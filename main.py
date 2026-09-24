import sys
import os
import logging
import subprocess
import threading
import time
import traceback
import logging .handlers
from PyQt6 .QtWidgets import (
QApplication ,QMainWindow ,QMessageBox ,QWidget ,
QVBoxLayout ,QHBoxLayout ,QPushButton ,QSystemTrayIcon ,QMenu ,
QFileDialog ,QInputDialog ,QLabel ,QLineEdit ,QAbstractButton 
)
from PyQt6 .QtCore import Qt ,QSettings ,QByteArray ,QTimer ,pyqtSignal ,QThread ,QObject ,QEvent ,QVariantAnimation ,QEasingCurve ,qInstallMessageHandler ,QtMsgType 
from PyQt6 .QtGui import QPainter ,QPixmap ,QShortcut ,QKeySequence 
from PyQt6 .QtGui import QIcon 

from config import (
SETTINGS ,THEME ,load_settings ,save_settings ,load_theme ,
load_tools ,load_categories ,save_tools ,save_categories ,DEFAULT_CATEGORIES ,
export_all_data ,import_all_data ,bump_weight
)
from utils import (
ensure_single_instance ,check_environment ,validate_java_path ,run_tool ,
is_tool_favorited ,add_favorite_tool ,remove_favorite_tool ,
save_main_window_geometry ,load_main_window_geometry ,save_main_window_state ,load_main_window_state ,
SearchWorker ,fuzzy_search ,get_favorite_tools ,get_recent_tools ,name_sort_key ,
reset_run_log_count
)
from widgets import (
TitleBar ,SearchBar ,CategoryPanel ,
ToolDialog ,SettingsDialog
)
from core .window_effect import WindowEffect
from core .modern_grid import ModernToolGrid
from services.tool_health import ToolHealthChecker
class _RateLimitingHandler (logging .Handler ):
    def __init__ (self ,inner :logging .Handler ,*,window_sec :float =10.0 ,max_per_key :int =20 ):
        super ().__init__ (level =inner .level )
        self ._inner =inner 
        self ._window =float (window_sec )
        self ._max =int (max_per_key )
        self ._state ={}
        self ._lock =threading .Lock ()

    def setFormatter (self ,fmt ):
        try :
            self ._inner .setFormatter (fmt )
        except Exception :
            pass 
        return super ().setFormatter (fmt )

    def _make_key (self ,record :logging .LogRecord ):
        try :
            msg =record .getMessage ()
        except Exception :
            msg =""
        if len (msg )>220 :
            msg =msg [:220 ]
        return (record .levelno ,record .name ,msg )

    def _emit_summary (self ,key ,suppressed :int ):
        try :
            levelno ,name ,msg =key 
            summary =logging .LogRecord (
            name =name ,
            level =levelno ,
            pathname ="",
            lineno =0 ,
            msg =f"[log-suppress] suppressed {suppressed} similar logs in last {int (self ._window )}s: {msg}",
            args =(),
            exc_info =None ,
            func =None ,
            sinfo =None ,
            )
            self ._inner .emit (summary )
        except Exception :
            pass 

    def emit (self ,record :logging .LogRecord ):
        now =time .time ()
        key =self ._make_key (record )
        with self ._lock :
            st =self ._state .get (key )
            if st is None :
                st =[now ,0 ,0 ]
                self ._state [key ]=st 
            win_start ,count ,supp =st [0 ],st [1 ],st [2 ]

            if now -win_start >=self ._window :
                if supp >0 :
                    self ._emit_summary (key ,supp )
                win_start =now 
                count =0 
                supp =0 

            if count <self ._max :
                st [0 ],st [1 ],st [2 ]=win_start ,count +1 ,supp 
                try :
                    self ._inner .emit (record )
                except Exception :
                    pass 
            else :
                st [0 ],st [1 ],st [2 ]=win_start ,count ,supp +1 


_LOG_PATH =os .path .join (os .path .dirname (os .path .abspath (__file__ )),"app.log")
_fmt =logging .Formatter ('%(asctime)s - %(levelname)s - %(message)s')
_file =logging .handlers .RotatingFileHandler (
_LOG_PATH ,maxBytes =2 *1024 *1024 ,backupCount =5 ,encoding ="utf-8"
)
_file .setFormatter (_fmt )
_console =logging .StreamHandler ()
_console .setFormatter (_fmt )

_file_rl =_RateLimitingHandler (_file ,window_sec =10.0 ,max_per_key =30 )
_console_rl =_RateLimitingHandler (_console ,window_sec =10.0 ,max_per_key =30 )

root_logger =logging .getLogger ()
root_logger .setLevel (logging .INFO )
root_logger .handlers .clear ()
root_logger .addHandler (_file_rl )
root_logger .addHandler (_console_rl )

logger =logging .getLogger (__name__ )


def install_log_hooks ():
    def _excepthook (exc_type ,exc ,tb ):
        try :
            lines =traceback .format_exception (exc_type ,exc ,tb )
            logger .error ("Uncaught exception:\n%s","".join (lines ))
        except Exception :
            pass 

        try :
            sys .__excepthook__ (exc_type ,exc ,tb )
        except Exception :
            pass 

    try :
        sys .excepthook =_excepthook 
    except Exception :
        pass 

    def _qt_msg_handler (mode ,context ,message ):
        try :
            try :
                msg =str (message )
            except Exception :
                msg =""

            if mode ==QtMsgType .QtCriticalMsg :
                logger .error ("QtCritical: %s",msg )
            elif mode ==QtMsgType .QtFatalMsg :
                logger .critical ("QtFatal: %s",msg )
        except Exception :
            pass 

    try :
        qInstallMessageHandler (_qt_msg_handler )
    except Exception :
        pass 


class ButtonHoverCursorFilter (QObject ):
    def eventFilter (self ,obj ,event ):
        try :
            if isinstance (obj ,QAbstractButton ):
                if event .type ()==QEvent .Type .Enter :
                    obj .setCursor (Qt .CursorShape .PointingHandCursor )
                elif event .type ()==QEvent .Type .Leave :
                    obj .unsetCursor ()
        except Exception :
            pass 
        return super ().eventFilter (obj ,event )

CURRENT_VERSION ='3.0'

def compute_category_counts (tools_list ):
    counts ={}
    counts [""]=len (tools_list )
    for t in tools_list :
        cat =t ["category"]
        counts [cat ]=counts .get (cat ,0 )+1 
    counts ["我的收藏"]=len (get_favorite_tools (tools_list ))
    counts ["最近启动"]=len ([k for k in SETTINGS .get ("recent_tools",[])if any (t ['name']==k [0 ]and t ['category']==k [1 ]for t in tools_list )])
    return counts 

class MainWindow (QMainWindow ):
    _toggle_visibility_signal =pyqtSignal ()
    def __init__ (self ):
        super ().__init__ ()
        if not ensure_single_instance ():
            sys .exit (0 )

        self ._perf_proc =None 

        self .tools =load_tools ()
        raw_categories =load_categories ()
        self .categories =list (raw_categories )
        for t in self .tools :
            if t ["category"]not in self .categories :
                self .categories .append (t ["category"])
        for special in ("最近启动","我的收藏"):
            if special not in self .categories :
                self .categories .insert (0 ,special )
        self .categories =self ._unique_ordered (self .categories )
        for special in ("最近启动","我的收藏"):
            if special not in self .categories :
                self .categories .insert (0 ,special )

        self .categories .sort (key =self ._cat_sort_key )
        if self .categories !=raw_categories :
            save_categories (self .categories )

        self .current_category =""
        self .search_text =""

        self ._is_restarting =False
        self ._dpi_adjusting =False

        self .health_checker =ToolHealthChecker ()
        self ._health_status ={}

        self .init_ui ()


        self ._btn_cursor_filter =ButtonHoverCursorFilter (self )
        QApplication .instance ().installEventFilter (self ._btn_cursor_filter )

        self .init_tray ()
        self .load_main_window_state_and_geometry ()
        self ._restore_sidebar_state ()
        self ._clamp_to_screen ()

        self ._toggle_visibility_signal .connect (self .toggle_window_visibility )
        QTimer .singleShot (3000 ,self .check_java_path )

        QTimer .singleShot (100 ,self .refresh_grid_layout )

    def _unique_ordered (self ,seq ):
        seen =set ()
        seen_add =seen .add 
        return [x for x in seq if not (x in seen or seen_add (x ))]

    def _cat_sort_key (self ,cat ):
        if cat =="最近启动":
            return 0
        if cat =="我的收藏":
            return 1
        return 2

    def showEvent (self ,event ):
        super ().showEvent (event )
        try :
            wh =self .windowHandle ()
            if wh and not hasattr (self ,'_screen_changed_connected'):
                wh .screenChanged .connect (self ._on_screen_changed )
                self ._screen_changed_connected =True
        except Exception :
            pass

    def _on_screen_changed (self ,screen ):
        try :
            if screen is None :
                return
            self ._dpi_adjusting =True
            available =screen .availableGeometry ()
            geo =self .geometry ()

            w =min (geo .width (),available .width ())
            h =min (geo .height (),available .height ())
            x =max (available .left (),min (geo .left (),available .right ()-w ))
            y =max (available .top (),min (geo .top (),available .bottom ()-h ))

            self .setGeometry (x ,y ,w ,h )
            QTimer .singleShot (200 ,self ._end_dpi_adjusting )
        except Exception :
            self ._dpi_adjusting =False

    def _end_dpi_adjusting (self ):
        self ._dpi_adjusting =False
        try :
            self .refresh_grid_layout ()
        except Exception :
            pass

    def _clamp_to_screen (self ):
        try :
            screen =self .screen ()
            if screen is None :
                screen =QApplication .primaryScreen ()
            if screen is None :
                return
            available =screen .availableGeometry ()
            geo =self .geometry ()
            w =min (geo .width (),available .width ())
            h =min (geo .height (),available .height ())
            x =max (available .left (),min (geo .left (),available .right ()-w ))
            y =max (available .top (),min (geo .top (),available .bottom ()-h ))
            self .setGeometry (x ,y ,w ,h )
        except Exception :
            pass

    def init_ui (self ):
        self .setWindowTitle ("zeroxf 工具箱 V4.0")
        self .setWindowIcon (QIcon ("config/fox.ico"))
        self .setWindowFlag (Qt .WindowType .FramelessWindowHint )
        self .resize (1400 ,800 )


        self .setAcceptDrops (True )

        central =QWidget ()
        self .setCentralWidget (central )
        main_lay =QVBoxLayout (central )
        main_lay .setContentsMargins (0 ,0 ,0 ,0 )
        main_lay .setSpacing (0 )

        self .title_bar =TitleBar (self )
        main_lay .addWidget (self .title_bar )

        content_layout =QHBoxLayout ()
        content_layout .setContentsMargins (0 ,0 ,0 ,0 )
        content_layout .setSpacing (20 )

        self .cat_panel =CategoryPanel (self .categories )
        self .cat_panel .setFixedWidth (240 )
        self .cat_panel .category_selected .connect (self .on_cat_selected )
        self .cat_panel .category_renamed .connect (self .on_cat_renamed )
        self .cat_panel .category_deleted .connect (self .on_cat_deleted )
        self .cat_panel .category_added .connect (self .on_cat_added )
        self .cat_panel .category_move .connect (self .on_cat_move )
        content_layout .addWidget (self .cat_panel )

        right_panel =QWidget ()
        rlayout =QVBoxLayout (right_panel )
        rlayout .setContentsMargins (0 ,0 ,0 ,0 )
        rlayout .setSpacing (0 )

        topbar =QWidget ()
        hl =QHBoxLayout (topbar )
        hl .setContentsMargins (10 ,10 ,10 ,10 )

        self .btn_sidebar =QPushButton ("◀")
        self .btn_sidebar .setObjectName ("noHoverBtn")
        self .btn_sidebar .setFixedWidth (40 )
        self .btn_sidebar .setToolTip ("收起 / 展开左侧分类栏")
        self .btn_sidebar .clicked .connect (self .toggle_sidebar )
        hl .addWidget (self .btn_sidebar )

        self .search_bar =SearchBar ()
        self .search_bar .search_changed .connect (self .on_search )
        hl .addWidget (self .search_bar )

        self .shortcut_find =QShortcut (QKeySequence ("Ctrl+F"),self )
        self .shortcut_find .activated .connect (self ._focus_search )

        btn_log =QPushButton ("日志")
        btn_log .setObjectName ("noHoverBtn")
        btn_log .setFixedWidth (80 )
        btn_log .clicked .connect (self .open_log_file )
        hl .addWidget (btn_log )

        btn_set =QPushButton ("设置")
        btn_set .setObjectName ("noHoverBtn")
        btn_set .setFixedWidth (80 )
        btn_set .clicked .connect (self .show_settings )
        hl .addWidget (btn_set )

        topbar .setLayout (hl )
        rlayout .addWidget (topbar )

        self .tool_grid =ModernToolGrid ()
        self .tool_grid .tool_run .connect (self .run_tool )
        self .tool_grid .tool_edit .connect (self .edit_tool )
        self .tool_grid .tool_delete .connect (self .delete_tool )
        self .tool_grid .favorite_changed .connect (self .on_favorite_changed )
        rlayout .addWidget (self .tool_grid )

        content_layout .addWidget (right_panel )
        main_lay .addLayout (content_layout )

        self .apply_theme ()
        self .update_cat_panel ()
        self .update_tool_grid ()

    def init_perf_monitor (self ):
        try :
            import psutil 
            self ._perf_proc =psutil .Process (os .getpid ())
            try :
                self ._perf_proc .cpu_percent (None )
            except Exception :
                pass 
        except Exception :
            self ._perf_proc =None 

        self ._perf_timer =QTimer (self )
        self ._perf_timer .setInterval (10000 )
        self ._perf_timer .timeout .connect (self .update_perf_monitor )
        self ._perf_timer .start ()
        self .update_perf_monitor ()


    def update_perf_monitor (self ):
        try :
            target =None 
            try :
                target =getattr (getattr (self ,"title_bar",None ),"perf_label",None )
            except Exception :
                target =None 

            if target is None :
                return 

            if self ._perf_proc is None :
                target .setText ("CPU N/A | 内存 N/A")
                return 

            cpu =0.0 
            mem_mb =0.0 
            mem_pct =0.0 
            try :
                cpu =float (self ._perf_proc .cpu_percent (None ))
            except Exception :
                cpu =0.0 
            try :
                mem_mb =float (self ._perf_proc .memory_info ().rss )/1024.0 /1024.0 
            except Exception :
                mem_mb =0.0 

            try :
                import psutil 
                vm =psutil .virtual_memory ()
                if getattr (vm ,"total",0 ):
                    mem_pct =(float (self ._perf_proc .memory_info ().rss )/float (vm .total ))*100.0 
            except Exception :
                mem_pct =0.0 

            target .setText (f"CPU {cpu:.1f}% | 内存 {mem_mb:.0f}MB({mem_pct:.1f}%)")
        except Exception :
            try :
                target =getattr (getattr (self ,"title_bar",None ),"perf_label",None )
                if target is not None :
                    target .setText ("CPU N/A | 内存 N/A")
            except Exception :
                pass 

    def _focus_search (self ):
        try :
            self .search_bar .search_input .setFocus ()
            self .search_bar .search_input .selectAll ()
        except Exception :
            pass 

    def toggle_sidebar (self ):
        try :
            delta =260   # 侧边栏宽 240 + 布局间距 20
            if self .cat_panel .isVisible ():
                self .cat_panel .hide ()
                self .move (self .x ()+delta ,self .y ())
                self .resize (self .width ()-delta ,self .height ())
                self .btn_sidebar .setText ("▶")
                SETTINGS ["sidebar_collapsed"]=True 
            else :
                self .move (self .x ()-delta ,self .y ())
                self .resize (self .width ()+delta ,self .height ())
                self .cat_panel .show ()
                self .btn_sidebar .setText ("◀")
                SETTINGS ["sidebar_collapsed"]=False 
            save_settings (SETTINGS )
        except Exception :
            pass 

    def _restore_sidebar_state (self ):
        try :
            if SETTINGS .get ("sidebar_collapsed",False ):
                self .cat_panel .hide ()
                self .btn_sidebar .setText ("▶")
        except Exception :
            pass 

    def open_log_file (self ):
        try :
            log_path =_LOG_PATH 
            if not os .path .isfile (log_path ):
                QMessageBox .information (self ,"打开日志",f"日志文件不存在:\n{log_path}")
                return 
            if sys .platform .startswith ("win"):
                os .startfile (log_path )
            else :
                subprocess .Popen (["xdg-open",log_path ])
        except Exception as e :
            QMessageBox .warning (self ,"打开日志",f"打开日志失败: {e}")

    def dragEnterEvent (self ,event ):
        try :
            if event .mimeData ().hasUrls ():
                event .acceptProposedAction ()
                return 
        except Exception :
            pass 
        event .ignore ()

    def dropEvent (self ,event ):
        try :
            if not event .mimeData ().hasUrls ():
                event .ignore ()
                return 

            paths =[]
            for u in event .mimeData ().urls ():
                try :
                    p =u .toLocalFile ()
                except Exception :
                    p =""
                if p :
                    paths .append (p )

            if not paths :
                event .ignore ()
                return 


            self ._open_add_tool_dialog_with_path (paths [0 ])
            event .acceptProposedAction ()
        except Exception as e :
            QMessageBox .warning (self ,"拖拽添加",str (e ))
            event .ignore ()

    def _open_add_tool_dialog_with_path (self ,path :str ):

        if getattr (self ,"current_category","")in ("","最近启动","我的收藏"):
            QMessageBox .information (self ,"提示","此工具分类不允许拖拽添加程序的工具卡片")
            return 


        if not os .path .isfile (path ):
            QMessageBox .information (self ,"提示","仅支持拖拽程序文件添加工具卡片")
            return 

        ext =os .path .splitext (path )[1 ].lower ()
        allowed ={".vbs",".bat",".py",".jar",".exe"}
        if ext not in allowed :
            QMessageBox .information (self ,"提示","仅支持拖拽 vbs/bat/py/jar/exe 文件")
            return 

        try :
            diag =ToolDialog (self .categories ,None ,self )

            base =os .path .basename (path .rstrip ("\\/"))
            name =os .path .splitext (base )[0 ]if os .path .isfile (path )else base 
            if hasattr (diag ,"ed_name"):
                diag .ed_name .setText (name )
            if hasattr (diag ,"ed_path"):
                diag .ed_path .setText (path )
            if hasattr (diag ,"cb_cat")and getattr (self ,"current_category","")not in ("","最近启动","我的收藏"):
                diag .cb_cat .setCurrentText (self .current_category )


            if hasattr (diag ,"cb_type"):
                type_map ={
                ".py":"Python",
                ".jar":"JAVA8",
                ".exe":"GUI应用",
                ".bat":"批处理",
                ".vbs":"批处理",
                }
                want =type_map .get (ext )
                if want :
                    diag .cb_type .setCurrentText (want )

            if diag .exec ():
                td =diag .get_tool_data ()
                if td ["type"]=="网页":
                    if not td ["name"]or not td ["url"]or not td ["category"]:
                        QMessageBox .warning (self ,"错误","请填写所有必填字段")
                    else :
                        if not self ._add_new_tool (td ):
                            QMessageBox .warning (self ,"错误","保存工具数据失败")
                else :
                    if not td ["name"]or not td ["category"]or not td ["path"]:
                        QMessageBox .warning (self ,"错误","请填写所有必填字段")
                    else :
                        if check_environment (td ["type"]):
                            if not self ._add_new_tool (td ):
                                QMessageBox .warning (self ,"错误","保存工具数据失败")

        finally :
            self .update_tool_grid ()

    def refresh_grid_layout (self ):
        try :
            self .tool_grid .adjust_card_size ()
        except Exception as e :
            logger .error (f"刷新卡片布局异常: {e}")

    def _recompute_page_size_if_needed (self ):
        return

    def resizeEvent (self ,e ):
        super ().resizeEvent (e )
        if getattr (self ,'_dpi_adjusting',False ):
            return
    def import_data (self ):
        try :
            path ,_ =QFileDialog .getOpenFileName (self ,"选择导入文件","","JSON Files (*.json)")
            if path :
                mode ,ok =QInputDialog .getItem (self ,"导入方式","请选择导入方式：",["合并","覆盖"],0 ,False )
                if ok :
                    import_all_data (path ,"overwrite"if mode =="覆盖"else "merge")
                    QMessageBox .information (self ,"导入","导入完成，请重启或刷新")
                    self .reload_data ()
        except Exception as e :
            QMessageBox .warning (self ,"导入错误",str (e ))

    def export_data (self ):
        try :
            path ,_ =QFileDialog .getSaveFileName (self ,"导出为","","JSON Files (*.json)")
            if path :
                export_all_data (path )
                QMessageBox .information (self ,"导出","导出完成！")
        except Exception as e :
            QMessageBox .warning (self ,"导出错误",str (e ))


    def reload_data (self ):
        self .tools =load_tools ()
        self .categories =load_categories ()
        self .apply_theme ()
        self .update_cat_panel ()
        self .update_tool_grid ()
        self .refresh_grid_layout ()

    def apply_theme (self ):
        from config import STYLESHEET 
        try :
            app =QApplication .instance ()
            if app is not None :
                app .setStyleSheet (STYLESHEET )
            else :
                self .setStyleSheet (STYLESHEET )
        except Exception :
            self .setStyleSheet (STYLESHEET )


    def paintEvent (self ,event ):
        if SETTINGS .get ("theme")=="custom_image":
            image_path =SETTINGS .get ("custom_bg_path","")
            if image_path and os .path .isfile (image_path ):
                painter =QPainter (self )
                pix =QPixmap (image_path )
                if not pix .isNull ():
                    scaled_pix =pix .scaled (self .width (),self .height (),
                    Qt .AspectRatioMode .KeepAspectRatioByExpanding ,
                    Qt .TransformationMode .SmoothTransformation )
                    x =(self .width ()-scaled_pix .width ())//2 
                    y =(self .height ()-scaled_pix .height ())//2 
                    painter .drawPixmap (x ,y ,scaled_pix )
        super ().paintEvent (event )


    def update_cat_panel (self ):
        ccount =compute_category_counts (self .tools )
        self .cat_panel .categories =self .categories 
        self .cat_panel .update_categories (self .categories ,ccount )


    def update_tool_grid (self ):

        from utils import get_favorite_tools ,get_recent_tools ,fuzzy_search 

        category =self .current_category 
        search_text =self .search_text 

        if category =="我的收藏":
            filtered =get_favorite_tools (self .tools )
        elif category =="最近启动":
            filtered =get_recent_tools (self .tools )
        elif category :
            filtered =[t for t in self .tools if t ['category']==category ]
        else :
            filtered =self .tools 

        if search_text :
            filtered =fuzzy_search (filtered ,search_text )

        if SETTINGS .get ("hide_web_tools",False ):
            filtered =[t for t in filtered if t .get ("type","")!="网页"]

        seen =set ()
        final =[]
        for t in filtered :
            k =(t ['name'],t ['category'])
            if k not in seen :
                seen .add (k )
                final .append (t )


        final .sort (key =lambda x :(
        -(1 if is_tool_favorited (x )else 0 ),
        -float (x .get ("weight",0 )or 0 ),
        name_sort_key (x .get ('name',''))
        ))


        display_tools =final

        self .tool_grid .set_final_tools (display_tools )


        self .refresh_grid_layout ()

    def on_cat_selected (self ,cat ):
        self .current_category =cat 
        self .update_tool_grid ()

    def on_cat_renamed (self ,old_name ,new_name ):
        old_name =str (old_name or "").strip ()
        new_name =str (new_name or "").strip ()
        if not new_name :
            QMessageBox .warning (self ,"错误","分类名称不能为空")
            return 
        norm =new_name .casefold ()
        if any (str (x ).strip ().casefold ()==norm for x in (self .categories or [])if str (x ).strip ()!=old_name ):
            QMessageBox .warning (self ,"错误",f"分类 '{new_name}' 已存在！")
            return 

        if old_name in self .categories :
            idx =self .categories .index (old_name )
            self .categories [idx ]=new_name 
        if save_tools (self .tools ):
            self .update_cat_panel ()
            self .update_tool_grid ()
        else :
            QMessageBox .warning (self ,"错误","保存工具数据失败")

    def on_cat_deleted (self ,cat ):
        if cat in ("我的收藏","最近启动"):
            QMessageBox .warning (self ,"提示","此分区不允许删除")
            return 
        tools_in_category =[t for t in self .tools if t ["category"]==cat ]
        if not tools_in_category :
            if cat in self .categories :
                self .categories .remove (cat )
                save_categories (self .categories )
                self .update_cat_panel ()
            return 
        else :
            msg =QMessageBox (self )
            msg .setWindowTitle ("确认删除")
            msg .setIcon (QMessageBox .Icon .Question )
            msg .setText (f"分类 '{cat}' 下共有 {len(tools_in_category)} 个工具，删除该分类会一并删除这些工具。\n是否继续？")
            msg .setStandardButtons (QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No )
            result =msg .exec ()

            if result ==QMessageBox .StandardButton .Yes :
                self .tools =[t for t in self .tools if t ["category"]!=cat ]
                if cat in self .categories :
                    self .categories .remove (cat )
                if save_tools (self .tools )and save_categories (self .categories ):
                    self .current_category =""
                    self .update_cat_panel ()
                    self .update_tool_grid ()
                else :
                    QMessageBox .warning (self ,"错误","保存数据失败，无法完成删除操作。")

    def on_cat_move (self ,cat ,direction ):
        if cat not in self .categories or cat in ("我的收藏","最近启动"):
            return 
        idx =self .categories .index (cat )
        new_idx =idx +direction 
        min_idx =2 if "最近启动"in self .categories and "我的收藏"in self .categories else 0 
        if new_idx <min_idx or new_idx >=len (self .categories ):
            return 
        self .categories .pop (idx )
        self .categories .insert (new_idx ,cat )
        save_categories (self .categories )
        self .update_cat_panel ()

    def on_cat_added (self ,_ ):
        new_cat ,ok =QInputDialog .getText (self ,"新建分类","请输入分类名称:")
        if ok and new_cat .strip ():
            new_cat =new_cat .strip ()

            norm =new_cat .casefold ()
            if any (str (x ).strip ().casefold ()==norm for x in (self .categories or [])):
                QMessageBox .warning (self ,"错误",f"分类 '{new_cat}' 已存在！")
                return 

            self .categories .append (new_cat )
            self .categories =sorted (set (self .categories ),key =self ._cat_sort_key )
            save_categories (self .categories )
            self .update_cat_panel ()

    def on_search (self ,txt ):
        self .search_text =(txt or "").strip ()
        self .update_tool_grid ()
        self .refresh_grid_layout ()

    def add_tool (self ):
        try :
            diag =ToolDialog (self .categories ,None ,self )
            if diag .exec ():
                td =diag .get_tool_data ()
                if td ["type"]=="网页":
                    if not td ["name"]or not td ["url"]or not td ["category"]:
                        QMessageBox .warning (self ,"错误","请填写所有必填字段")
                    else :
                        if not self ._add_new_tool (td ):
                            QMessageBox .warning (self ,"错误","保存工具数据失败")
                else :
                    if not td ["name"]or not td ["category"]or not td ["path"]:
                        QMessageBox .warning (self ,"错误","请填写所有必填字段")
                    else :
                        if check_environment (td ["type"]):
                            if not self ._add_new_tool (td ):
                                QMessageBox .warning (self ,"错误","保存工具数据失败")

        except Exception as e :
            QMessageBox .warning (self ,"添加工具异常",str (e ))
        self .update_tool_grid ()

    def _add_new_tool (self ,td ):

        td_name =str (td .get ('name','')).strip ()
        norm =td_name .casefold ()
        for ex in (self .tools or []):
            ex_name =str (ex .get ('name','')).strip ()
            if ex_name and ex_name .casefold ()==norm :
                QMessageBox .warning (self ,"错误","已存在同名工具，工具名称必须唯一")
                return True 

        self .tools .append (td )
        if td ["category"]not in self .categories :
            self .categories .append (td ["category"])
            self .categories =sorted (set (self .categories ),key =self ._cat_sort_key )
            save_categories (self .categories )

        if save_tools (self .tools ):
            self .update_cat_panel ()
            self .update_tool_grid ()
            self .update_tool_grid ()
            return True
        return False 

    def edit_tool (self ,tool_data ):
        try :
            diag =ToolDialog (self .categories ,tool_data ,self )
            old_name =tool_data ['name']
            if diag .exec ():
                newinfo =diag .get_tool_data ()


                new_name =str (newinfo .get ('name','')).strip ()
                norm =new_name .casefold ()
                idx =self .tools .index (tool_data )
                for i ,ex in enumerate (self .tools or []):
                    if i ==idx :
                        continue 
                    ex_name =str (ex .get ('name','')).strip ()
                    if ex_name and ex_name .casefold ()==norm :
                        QMessageBox .warning (self ,"错误","已存在同名工具，工具名称必须唯一")
                        return 
                self .tools [idx ]=newinfo 

                if not save_tools (self .tools ):
                    QMessageBox .warning (self ,"错误","保存失败！")
                else :
                    self .update_cat_panel ()
                    self .update_tool_grid ()

        except Exception as e :
            QMessageBox .warning (self ,"编辑工具异常",str (e ))
        self .update_tool_grid ()

    def delete_tool (self ,tool_data ):
        msg =QMessageBox (self )
        msg .setWindowTitle ("确认删除")
        msg .setText (f"确定删除工具 '{tool_data['name']}' 吗？")
        msg .setIcon (QMessageBox .Icon .Question )
        msg .setStandardButtons (QMessageBox .StandardButton .Yes |QMessageBox .StandardButton .No )
        r =msg .exec ()
        if r ==QMessageBox .StandardButton .Yes :
            cat =tool_data ["category"]
            self .tools .remove (tool_data )

            if not save_tools (self .tools ):
                QMessageBox .warning (self ,"错误","保存工具数据失败")
                return 

            nm =tool_data ['name']
            remain =[t for t in self .tools if t ["category"]==cat ]
            if not remain and cat not in DEFAULT_CATEGORIES :
                if cat in self .categories :
                    self .categories .remove (cat )
                save_categories (self .categories )

            self .update_cat_panel ()
            self .update_tool_grid ()
            self .refresh_grid_layout ()

    def run_tool (self ,tool_data ):
        ok =False 
        try :
            ok =run_tool (tool_data )
        except Exception as e :
            QMessageBox .warning (self ,"错误",f"运行失败:{e}")

        if ok :
            try :
                name =str (tool_data .get ("name","")).strip ()
                cat =str (tool_data .get ("category","")).strip ()
                for t in self .tools :
                    if str (t .get ("name","")).strip ()==name and str (t .get ("category","")).strip ()==cat :
                        # 计数写进 weights.json（gitignore），**不写 tools.json** ——
                        # 后者被 git 跟踪，写进去会让工作区每启动一次工具就脏一次
                        bump_weight (t )
                        try :
                            t ["weight"]=float (t .get ("weight",0 )or 0 )+1.0
                        except Exception :
                            t ["weight"]=1.0
                        self .update_tool_grid ()
                        break
            except Exception :
                pass 

    def on_favorite_changed (self ,tool_data ,is_fav ):
        self .update_cat_panel ()
        self .update_tool_grid ()
        self .refresh_grid_layout ()

    def show_settings (self ):
        diag =SettingsDialog (self )
        diag .settings_changed .connect (self .on_settings_changed )

        diag .exec ()

    def on_settings_changed (self ,new_s ):
        SETTINGS .clear ()
        SETTINGS .update (new_s )
        self .apply_theme ()
        self .update_tool_grid ()
        self .refresh_grid_layout ()

    def toggle_window_visibility (self ):
        try :
            if self .isVisible ():
                if self .windowState ()&Qt .WindowState .WindowMinimized :
                    self .showNormal ()
                    self .activateWindow ()
                    self .raise_()
                else :
                    self .showMinimized ()
            else :
                self .showNormal ()
                self .activateWindow ()
                self .raise_()
        except Exception as e :
            logger .error (f"切换窗口可见性失败: {e}")

    def restart_application (self ):
        self ._is_restarting =True 

        try :
            from config import SETTINGS as _SETTINGS 
            save_settings (_SETTINGS )
        except Exception :

            pass 


        import subprocess 
        import sys 


        loader_path =os .path .join (os .path .dirname (os .path .abspath (__file__ )),"loader.py")
        python_exe =sys .executable 


        if sys .platform .startswith ("win"):

            subprocess .Popen ([python_exe ,loader_path ],creationflags =subprocess .CREATE_NEW_PROCESS_GROUP ,close_fds =True )
        else :

            pid =os .fork ()
            if pid >0 :

                os ._exit (0 )
            else :

                os .setsid ()
                pid =os .fork ()
                if pid >0 :
                    os ._exit (0 )
                else :

                    os .execv (python_exe ,[python_exe ,loader_path ])


        self .force_quit ()

    def check_java_path (self ):
        try :
            validate_java_path ()
        except Exception as e :
            QMessageBox .warning (self ,"Java路径",f"检测Java路径失败: {e}")

    def init_tray (self ):
        self .tray_icon =QSystemTrayIcon (self )
        self .tray_icon .setIcon (QIcon ("config/fox.ico"))
        m =QMenu ()

        try :
            anim =QVariantAnimation (m )
            anim .setDuration (140 )
            anim .setEasingCurve (QEasingCurve .Type .OutCubic )

            def _on_val (v ):
                t =float (v )
                try :
                    m .setWindowOpacity (t )
                except Exception :
                    pass 
                try :
                    p =m .pos ()
                    m .move (p .x (),p .y ()+int (6 *(1.0 -t )))
                except Exception :
                    pass 

            anim .valueChanged .connect (_on_val )

            def _start_anim ():
                try :
                    anim .stop ()
                except Exception :
                    pass 
                try :
                    m .setWindowOpacity (0.0 )
                except Exception :
                    return 
                anim .setStartValue (0.0 )
                anim .setEndValue (1.0 )
                anim .start ()

            m .aboutToShow .connect (_start_anim )
        except Exception :
            pass 

        act_show =m .addAction ("显示主窗口")
        act_show .triggered .connect (self .show_and_focus )
        act_exit =m .addAction ("退出程序")
        act_exit .triggered .connect (self .force_quit )
        self .tray_icon .setContextMenu (m )
        self .tray_icon .activated .connect (self .on_tray_activated )
        self .tray_icon .show ()

    def show_and_focus (self ):
        self .show ()
        self .tray_icon .hide ()

    def on_tray_activated (self ,reason ):
        if reason ==QSystemTrayIcon .ActivationReason .DoubleClick :
            self .show_and_focus ()

    def _cleanup_before_exit (self ):

        if getattr (self ,"_is_exiting",False ):
            return 
        self ._is_exiting =True 

        try :
            if hasattr (self ,"tray_icon")and self .tray_icon :
                try :
                    self .tray_icon .hide ()
                except Exception :
                    pass 
        except Exception :
            pass 

    def force_quit (self ):
        try :
            self ._cleanup_before_exit ()
        except Exception :
            pass 
        try :
            QApplication .quit ()
        except Exception :
            pass 

        os ._exit (0 )

    def closeEvent (self ,e ):
        save_main_window_geometry (self .saveGeometry ())
        save_main_window_state (self .saveState ())


        if getattr (self ,"_is_restarting",False ):
            e .accept ()
            self .force_quit ()
            return 

        mode =SETTINGS .get ("exit_mode","ask")
        if mode =="ask":
            msg =QMessageBox (self )
            msg .setWindowTitle ("退出确认")
            msg .setText ("确定要退出吗？")
            msg .setIcon (QMessageBox .Icon .Question )
            b1 =msg .addButton ("最小化到托盘",QMessageBox .ButtonRole .ActionRole )
            b2 =msg .addButton ("退出程序",QMessageBox .ButtonRole .AcceptRole )
            b3 =msg .addButton ("取消",QMessageBox .ButtonRole .RejectRole )
            msg .setDefaultButton (b3 )
            for btn in (b1 ,b2 ,b3 ):
                btn .setObjectName ("dialogBtn")
            msg .exec ()
            if msg .clickedButton ()==b1 :
                e .ignore ()
                self .hide ()
                self .tray_icon .show ()
            elif msg .clickedButton ()==b2 :
                e .accept ()
                self .force_quit ()
            else :
                e .ignore ()
        elif mode =="tray":
            e .ignore ()
            self .hide ()
            self .tray_icon .show ()
        else :
            e .accept ()
            self .force_quit ()

    def open_notebook (self ):
        try :
            notepad_path =os .path .join ("notepad","eDiary.exe")
            notepad_path =os .path .abspath (notepad_path )
            if sys .platform .startswith ("win"):
                os .startfile (notepad_path )
            else :
                subprocess .Popen ([notepad_path ])
        except Exception as e :
            QMessageBox .warning (self ,"错误",f"运行失败: {e}")

    def check_tools_health (self ):
        try :
            self ._health_status =self .health_checker .check_all (self .tools )
            missing =self .health_checker .get_missing_tools (self .tools )
            if missing :
                names =[t .get ("name","")for t in missing [:5 ]]
                logger .info (f"工具健康检查: {len(missing)} 个工具路径缺失 ({', '.join(names)}...)")
            self .update_tool_grid ()
        except Exception as e :
            logger .warning (f"工具健康检查失败: {e}")

    def load_main_window_state_and_geometry (self ):
        geo_bytes =load_main_window_geometry ()
        state_bytes =load_main_window_state ()
        if geo_bytes :
            self .restoreGeometry (QByteArray (geo_bytes ))
        if state_bytes :
            self .restoreState (QByteArray (state_bytes ))
        self ._clamp_to_screen ()

def main ():
    QApplication .setHighDpiScaleFactorRoundingPolicy (
        Qt .HighDpiScaleFactorRoundingPolicy .PassThrough
    )
    os .environ ["QT_ENABLE_HIGHDPI_SCALING"]="1"
    os .environ ["QT_SCALE_FACTOR_ROUNDING_POLICY"]="PassThrough"

    install_log_hooks ()
    reset_run_log_count ()
    app =QApplication (sys .argv )
    w =MainWindow ()
    w .show ()
    sys .exit (app .exec ())

if __name__ =="__main__":
    main ()
