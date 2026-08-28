import os
import json
import shutil
import tempfile

DEFAULT_CATEGORIES =[
"最近启动",
"我的收藏",
"WebShell管理工具",
"信息收集工具",
"抓包与代理工具",
"漏洞扫描与利用工具",
"框架漏洞利用工具",
"爆破工具",
"免杀工具",
"后渗透工具",
"其他工具",
"网页工具"
]

TOOL_TYPES =(
"Python",
"JAVA8",
"JAVA11",
"GUI应用",
"命令行",
"批处理",
"PowerShell",
"网页"
)

CYBERPUNK_THEME ={
"primary":"#00857E",
"secondary":"#2C0236",
"background":"#080018",
"surface":"#120240",
"content_bg":"#1D0633",
"text":"#F2F2F2",
"text_secondary":"#AADDDD",
"border":"#9F00FF",
"hover":"#00A194",
"selected":"#BA00FF80",
"error":"#FF0066",
"success":"#00ffa3",
"header":"#1D0633",
"toolbar":"#1D0633",
"dropdown":"#350066",
"title_bar":"#1D0633",
"title_bar_text":"#F2F2F2",
"title_btn_hover":"#43106B",
"title_btn_close_hover":"#FF0066",
"card_bg":"#120240",
"category_bg":"#1D0633",
"menu_button_text":"#00FFF7"
}

RED_BLUE_GLASS_THEME ={
"primary":"#FF3344",
"secondary":"#002aff",
"background":(
"qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
"stop:0 rgba(255, 51, 68, 0.45), stop:1 rgba(0, 42, 255, 0.45))"
),
"surface":"rgba(255, 255, 255, 0.14)",
"content_bg":"rgba(255, 255, 255, 0.09)",
"text":"#FFFFFF",
"text_secondary":"#EEEEEE",
"border":"rgba(255, 255, 255, 0.28)",
"hover":"rgba(200, 180, 255, 0.20)",
"selected":"rgba(225, 215, 255, 0.24)",
"error":"#FF3355",
"success":"#33FF88",
"header":"rgba(255, 255, 255, 0.12)",
"toolbar":"rgba(255, 255, 255, 0.12)",
"dropdown":"rgba(55, 30, 105, 0.92)",
"title_bar":"rgba(255, 255, 255, 0.18)",
"title_bar_text":"#FFFFFF",
"title_btn_hover":"rgba(255, 255, 255, 0.28)",
"title_btn_close_hover":"#AA0033",
"card_bg":"rgba(205, 190, 255, 0.16)",
"category_bg":"rgba(255, 255, 255, 0.10)"
}

Titanium_silver_THEME ={
"primary":"#6F7A89",
"secondary":"#B0B8C1",
"background":"#23272E",
"surface":"#343942",
"content_bg":"#343942",
"text":"#E3E8EE",
"text_secondary":"#AAB4C0",
"border":"#5A626D",
"hover":"#4B535E",
"selected":"#6F7A89AA",
"error":"#D36C6C",
"success":"#80B09C",
"header":"#23272E",
"toolbar":"#343942",
"dropdown":"#343942",
"title_bar":"#23272E",
"title_bar_text":"#E3E8EE",
"title_btn_hover":"#B0B8C1",
"title_btn_close_hover":"#D36C6C",
"card_bg":"#343942",
"category_bg":"#23272E"
}

SANDSTONE_GRAY_THEME ={
"primary":"#B8A47E",
"secondary":"#CFC3B1",
"background":"#F8F6F1",
"surface":"#EFE8DE",
"content_bg":"#EFE8DE",
"text":"#665B4E",
"text_secondary":"#A09281",
"border":"#D7CFC1",
"hover":"#EAD9B7",
"selected":"#B8A47E44",
"error":"#C97E7E",
"success":"#7EBC8C",
"header":"#F8F6F1",
"toolbar":"#EFE8DE",
"dropdown":"#EFE8DE",
"title_bar":"#F8F6F1",
"title_bar_text":"#665B4E",
"title_btn_hover":"#CFC3B1",
"title_btn_close_hover":"#C97E7E",
"card_bg":"#FFFFFF",
"category_bg":"#EFE8DE",
"button_text":"#FFFFFF"
}

LIQUID_GLASS_THEME ={
"primary":"#007AFF",
"secondary":"#F2F2F7",
"background":"#F2F2F7",
"surface":"#FFFFFF",
"content_bg":"rgba(255, 255, 255, 0.8)",
"text":"#000000",
"text_secondary":"#3C3C43",
"border":"rgba(60, 60, 67, 0.15)",
"hover":"#F0F8FF",
"selected":"#E1F0FF",
"error":"#FF3B30",
"success":"#34C759",
"header":"transparent",
"toolbar":"transparent",
"dropdown":"#FFFFFF",
"title_bar":"transparent",
"title_bar_text":"#000000",
"title_btn_hover":"rgba(0, 0, 0, 0.05)",
"title_btn_close_hover":"#FF3B30",
"card_bg":"#FFFFFF",
"category_bg":"rgba(255, 255, 255, 0.6)",
"menu_button_text":"#007AFF",
"scrollbar":"#C1C1C1",
"scrollbar_hover":"#A8A8A8",
"button_text":"#FFFFFF"
}

PERFORMANCE_THEME ={
"primary":"#3B82F6",
"secondary":"#111827",
"background":"#0F172A",
"surface":"#111827",
"content_bg":"#0F172A",
"text":"#E5E7EB",
"text_secondary":"#94A3B8",
"border":"#1F2937",
"hover":"#172033",
"selected":"#3B82F633",
"error":"#EF4444",
"success":"#22C55E",
"header":"#111827",
"toolbar":"#111827",
"dropdown":"#111827",
"title_bar":"#111827",
"title_bar_text":"#E5E7EB",
"title_btn_hover":"#1F2937",
"title_btn_close_hover":"#B91C1C",
"card_bg":"#111827",
"category_bg":"#0B1220",
"scrollbar":"#475569",
"scrollbar_hover":"#64748B",
"button_text":"#FFFFFF"
}

THEMES ={
"dark":{
"primary":"#2B5DCD",
"secondary":"#1E1E1E",
"background":"#121212",
"surface":"#000000",
"content_bg":"#000000",
"text":"#FFFFFF",
"text_secondary":"#B3B3B3",
"border":"#2F2F2F",
"hover":"#333333",
"selected":"#2B5DCD33",
"error":"#CF6679",
"success":"#4CAF50",
"header":"#000000",
"toolbar":"#000000",
"dropdown":"#000000",
"title_bar":"#000000",
"title_bar_text":"#FFFFFF",
"title_btn_hover":"#383838",
"title_btn_close_hover":"#E81123",
"card_bg":"#000000",
"category_bg":"#000000"
},
"light":{
"primary":"#A69F95",
"secondary":"#F5F5F5",
"background":"#FFFFFF",
"surface":"#FFFFFF",
"content_bg":"#FFFFFF",
"text":"#333333",
"text_secondary":"#666666",
"border":"#E0E0E0",
"hover":"#F5F5F5",
"selected":"#A69F9533",
"error":"#D9534F",
"success":"#5CB85C",
"header":"#FFFFFF",
"toolbar":"#FFFFFF",
"dropdown":"#FFFFFF",
"title_bar":"#FFFFFF",
"title_bar_text":"#333333",
"title_btn_hover":"#F0F0F0",
"title_btn_close_hover":"#B92727",
"card_bg":"#FFFFFF",
"category_bg":"#FFFFFF",
"button_text":"#FFFFFF"
},
"eye_care":{
"primary":"#8FBF60",
"secondary":"#F3F3E7",
"background":"#F7F6E9",
"surface":"#F7F6E9",
"content_bg":"#F7F6E9",
"text":"#3B3B2A",
"text_secondary":"#6D6D57",
"border":"#B3B190",
"hover":"#E8E7D3",
"selected":"#8FBF6044",
"error":"#C9302C",
"success":"#5CB85C",
"header":"#F7F6E9",
"toolbar":"#F7F6E9",
"dropdown":"#F7F6E9",
"title_bar":"#F7F6E9",
"title_bar_text":"#3B3B2A",
"title_btn_hover":"#E8E7D3",
"title_btn_close_hover":"#AF3F3F",
"card_bg":"#F7F6E9",
"category_bg":"#F7F6E9",
"button_text":"#3B3B2A"
},
"pink":{
"primary":"#FF7EB6",
"secondary":"#FFF0F7",
"background":"#FFF9FB",
"surface":"#FFF9FB",
"content_bg":"#FFF9FB",
"text":"#4F4F4F",
"text_secondary":"#767676",
"border":"#FFE4EF",
"hover":"#FFF0F7",
"selected":"#FF7EB644",
"error":"#FF4E6E",
"success":"#4CAF50",
"header":"#FFF9FB",
"toolbar":"#FFF9FB",
"dropdown":"#FFF9FB",
"title_bar":"#FFF9FB",
"title_bar_text":"#4F4F4F",
"title_btn_hover":"#FFE4EF",
"title_btn_close_hover":"#FF4E6E",
"card_bg":"#FFFFFF",
"category_bg":"#FFF9FB",
"button_text":"#FFFFFF"
},
"blue":{
"primary":"#2196F3",
"secondary":"#E3F2FD",
"background":"#EAF2F8",
"surface":"#FFFFFF",
"content_bg":"#EAF2F8",
"text":"#2C3E50",
"text_secondary":"#546E7A",
"border":"#BBDEFB",
"hover":"#E3F2FD",
"selected":"#2196F333",
"error":"#F44336",
"success":"#4CAF50",
"header":"#EAF2F8",
"toolbar":"#EAF2F8",
"dropdown":"#FFFFFF",
"title_bar":"#EAF2F8",
"title_bar_text":"#2C3E50",
"title_btn_hover":"#E3F2FD",
"title_btn_close_hover":"#EF5350",
"card_bg":"#FFFFFF",
"category_bg":"#EAF2F8",
"button_text":"#FFFFFF"
},
"cyberpunk":CYBERPUNK_THEME ,
"red_blue_glass":RED_BLUE_GLASS_THEME ,
"Titanium_silver":Titanium_silver_THEME ,
"sandstone_gray":SANDSTONE_GRAY_THEME ,
"performance":PERFORMANCE_THEME ,
"liquid_glass":LIQUID_GLASS_THEME ,
"custom_image":{}
}

def load_theme (theme_name ):
    if theme_name =="custom_image":

        base =dict (THEMES .get ("dark",{}))
        base .update (THEMES .get ("red_blue_glass",{}))
        base ["background"]="transparent"
        return base 

    base =dict (THEMES .get ("dark",{}))
    theme =THEMES .get (theme_name )
    if isinstance (theme ,dict ):
        base .update (theme )

    return base 

DEFAULT_SETTINGS ={
"confirm_exit":False ,
"theme":"liquid_glass",
"font_size":12 ,
"java8_path":"Java_path/Java_8_win/bin",
"java11_path":"Java_path/Java_11_win/bin",
"python_path":"python3/python.exe",
"exit_mode":"quit",
"display_mode":"scroll",
"cli_python_interpreters":[],
"cli_java_interpreters":[],
"favorite_tools":[],
"recent_tools":[],
"main_window_geometry":None ,
"main_window_state":None ,
"sidebar_collapsed":False ,
"hide_web_tools":False ,
"auto_theme_mode":"manual",
"custom_bg_path":"",
"screenshot_hotkey":"",
"quick_open_hotkey":"",
"terminal_save_prompt":"prompt_if_content",
"terminal_default_shell":"cmd",
"terminal_font_size":10
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "config", "settings.json")
TOOLS_FILE = os.path.join(BASE_DIR, "config", "tools.json")
CATEGORIES_FILE = os.path.join(BASE_DIR, "config", "categories.json")
HOTKEYS_FILE = os.path.join(BASE_DIR, "config", "hotkeys.json")

def _atomic_write_json (filepath :str ,data ):
    dirpath =os .path .dirname (filepath )
    if dirpath and not os .path .exists (dirpath ):
        os .makedirs (dirpath ,exist_ok =True )

    fd ,tmp_path =tempfile .mkstemp (suffix =".tmp",dir =dirpath ,prefix =".th3_")
    try :
        with os .fdopen (fd ,"w",encoding ="utf-8")as f :
            json .dump (data ,f ,ensure_ascii =False ,indent =2 )
            f .flush ()
            os .fsync (f .fileno ())
    except Exception :
        try :
            os .unlink (tmp_path )
        except Exception :
            pass
        raise

    bak_path =filepath +".bak"
    if os .path .exists (filepath ):
        try :
            shutil .copy2 (filepath ,bak_path )
        except Exception :
            pass
    os .replace (tmp_path ,filepath )

def load_settings ():
    if not os .path .exists (os .path .join (BASE_DIR ,"config")):
        os .makedirs (os .path .join (BASE_DIR ,"config"),exist_ok =True )
    if not os .path .isfile (SETTINGS_FILE ):
        try :
            _atomic_write_json (SETTINGS_FILE ,DEFAULT_SETTINGS )
        except Exception as err :
            print (f"生成默认settings.json时出错: {err}")
        return DEFAULT_SETTINGS .copy ()
    else :
        try :
            with open (SETTINGS_FILE ,"r",encoding ="utf-8")as f :
                user_cfg =json .load (f )
            final_cfg ={**DEFAULT_SETTINGS ,**user_cfg }
            if "cli_python_interpreters"not in final_cfg :
                final_cfg ["cli_python_interpreters"]=[]
            if "cli_java_interpreters"not in final_cfg :
                final_cfg ["cli_java_interpreters"]=[]


            legacy =final_cfg .get ("custom_interpreters",None )
            if isinstance (legacy ,list )and legacy :
                py_names ={str (x .get ("name",""))for x in final_cfg .get ("cli_python_interpreters",[])if isinstance (x ,dict )}
                java_names ={str (x .get ("name",""))for x in final_cfg .get ("cli_java_interpreters",[])if isinstance (x ,dict )}
                for ci in legacy :
                    if not isinstance (ci ,dict ):
                        continue 
                    name =str (ci .get ("name","")).strip ()
                    path =str (ci .get ("path","")).strip ()
                    typ =str (ci .get ("type","")).strip ().lower ()
                    if not name or not path :
                        continue 
                    if typ =="python":
                        if name not in py_names :
                            final_cfg ["cli_python_interpreters"].append ({"name":name ,"path":path })
                            py_names .add (name )
                    elif typ =="java":
                        if name not in java_names :
                            final_cfg ["cli_java_interpreters"].append ({"name":name ,"path":path })
                            java_names .add (name )


            if "custom_interpreters"in final_cfg :
                try :
                    del final_cfg ["custom_interpreters"]
                except Exception :
                    pass 
            if "favorite_tools"not in final_cfg :
                final_cfg ["favorite_tools"]=[]
            if "recent_tools"not in final_cfg :
                final_cfg ["recent_tools"]=[]
            if "main_window_geometry"not in final_cfg :
                final_cfg ["main_window_geometry"]=None 
            if "main_window_state"not in final_cfg :
                final_cfg ["main_window_state"]=None 
            if "auto_theme_mode"not in final_cfg :
                final_cfg ["auto_theme_mode"]="manual"
            if "custom_bg_path"not in final_cfg :
                final_cfg ["custom_bg_path"]=""
            return final_cfg 
        except Exception as err :
            print (f"读取settings.json出错: {err}")
            return DEFAULT_SETTINGS .copy ()

def save_settings (settings_dict :dict ):
    try :

        if not os .path .exists (os .path .join (BASE_DIR ,"config")):
            os .makedirs (os .path .join (BASE_DIR ,"config"),exist_ok =True )


        if "custom_interpreters"in settings_dict :
            try :
                del settings_dict ["custom_interpreters"]
            except Exception :
                pass
        _atomic_write_json (SETTINGS_FILE ,settings_dict )
        return True
    except Exception as err :
        print (f"保存settings.json出错: {err}")
        return False 

def fix_paths (settings_dict :dict ):
    for key in ["python_path","java8_path","java11_path"]:
        val =settings_dict .get (key ,"").strip ()
        if val and not os .path .isabs (val ):
            abs_val =os .path .abspath (val )
            settings_dict [key ]=abs_val 
    for arr_key in ["cli_python_interpreters","cli_java_interpreters"]:
        if arr_key in settings_dict and isinstance (settings_dict [arr_key ],list ):
            for ci in settings_dict [arr_key ]:
                if isinstance (ci ,dict )and "path"in ci and ci ["path"]and not os .path .isabs (ci ["path"]):
                    ci ["path"]=os .path .abspath (ci ["path"])

SETTINGS =load_settings ()
fix_paths (SETTINGS )
SETTINGS ["theme"]="liquid_glass"
SETTINGS ["custom_bg_path"]=""
SETTINGS ["exit_mode"]="quit"
SETTINGS ["confirm_exit"]=False
THEME =load_theme (SETTINGS .get ("theme","dark"))

_dropdown_bg =THEME .get ("dropdown",THEME .get ("surface","#222"))
try :
    _db =str (_dropdown_bg ).strip ().lower ()
    if _db in ("transparent","rgba(0, 0, 0, 0)","rgba(0,0,0,0)"):
        _dropdown_bg ="rgba(20, 20, 28, 0.92)"
except Exception :
    _dropdown_bg ="rgba(20, 20, 28, 0.92)"

STYLESHEET =(
f"QMainWindow {{"
f"    background: {THEME['background'] if SETTINGS.get('theme') in ('red_blue_glass','custom_image') else (THEME['background'] if SETTINGS.get('theme')!='custom_image' else 'transparent')};"
f"    border-radius: 16px;"
f"}}"
f"QWidget {{"
f"    color: {THEME['text']};"
f"    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;"
f"    font-size: 13px;"
f"}}"
f"QWidget#categoryContainer {{"
f"    background-color: {THEME['category_bg']};"
f"    border-right: 1px solid {THEME['border']};"
f"}}"
f"QWidget#toolCard {{"
f"    background-color: {THEME['card_bg']};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 12px;"
f"    margin: 4px;"
f"    padding: 8px;"
f"}}"
f"QWidget#toolCard:hover {{"
f"    border: 1px solid {THEME['primary']};"
f"    background-color: {THEME['hover']};"
f"}}"
f"QWidget#toolGridContainer {{"
f"    background-color: {THEME['content_bg']};"
f"}}"
f"QWidget#titleBar {{"
f"    background-color: {THEME['title_bar']};"
f"    border-bottom: 1px solid {THEME['border']};"
f"    border-top-left-radius: 16px;"
f"    border-top-right-radius: 16px;"
f"}}"
f"QWidget#titleBar QLabel {{"
f"    color: {THEME['title_bar_text']};"
f"    font-size: 15px;"
f"    font-weight: 600;"
f"    background-color: transparent;"
f"}}"
f"QPushButton#titleButton {{"
f"    background-color: transparent;"
f"    border: none;"
f"    border-radius: 8px;"
f"    min-width: 40px;"
f"    max-width: 40px;"
f"    min-height: 28px;"
f"    max-height: 28px;"
f"    color: {THEME['title_bar_text']};"
f"}}"
f"QPushButton#titleButton:hover {{"
f"    background-color: transparent;"
f"}}"
f"QPushButton#closeButton:hover {{"
f"    background-color: transparent;"
f"    color: {THEME['title_bar_text']};"
f"}}"
f"QToolBar {{"
f"    background-color: {THEME['toolbar']};"
f"    border: none;"
f"    padding: 8px;"
f"}}"
f"QToolButton {{"
f"    background-color: transparent;"
f"    color: {THEME['text']};"
f"    border: 1px solid transparent;"
f"    border-radius: 8px;"
f"    padding: 6px;"
f"}}"
f"QToolButton:hover {{"
f"    background-color: transparent;"
f"}}"
f"QPushButton {{"
f"    background-color: {THEME['primary']};"
f"    color: {THEME.get('button_text', '#FFFFFF')};"
f"    border: none;"
f"    border-radius: 8px;"
f"    padding: 8px 16px;"
f"    font-weight: 600;"
f"}}"
f"QPushButton:hover {{"
f"    background-color: {THEME['primary']};"
f"}}"
f"QPushButton:pressed {{"
f"    background-color: {THEME['primary']};"
f"}}"
f"QPushButton:focus {{"
f"    background-color: {THEME['primary']};"
f"}}"
f"QPushButton#noHoverBtn:hover {{"
f"    background-color: {THEME['primary']};"
f"}}"
f"QPushButton#noHoverBtn:pressed {{"
f"    background-color: {THEME['primary']};"
f"}}"
f"QPushButton#noHoverBtn:focus {{"
f"    border: none;"
f"    background-color: {THEME['primary']};"
f"}}"
f"QToolTip {{"
f"    background-color: {THEME['card_bg']};"
f"    color: {THEME['text']};"
f"    border: 1px solid {THEME['primary']};"
f"    border-radius: 12px;"
f"    padding: 10px 12px;"
f"    font-size: 12px;"
f"}}"
f"QMenu {{"
f"    background-color: {_dropdown_bg};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 12px;"
f"    padding: 6px;"
f"}}"
f"QMenu::item {{"
f"    padding: 8px 14px;"
f"    border-radius: 10px;"
f"    color: {THEME['text']};"
f"}}"
f"QMenu::item:disabled {{"
f"    color: {THEME.get('text_secondary', THEME['text'])};"
f"}}"
f"QMenu::item:hover {{"
f"    background-color: {THEME['hover']};"
f"    color: {THEME['text']};"
f"}}"
f"QMenu::item:selected {{"
f"    background-color: {THEME['hover']};"
f"    color: {THEME['text']};"
f"}}"
f"QMenu::separator {{"
f"    height: 1px;"
f"    background-color: {THEME['border']};"
f"    margin: 4px 8px;"
f"}}"
f"QPushButton#categoryBtn {{"
f"    background-color: transparent;"
f"    text-align: left;"
f"    font-size: 13px;"
f"    padding: 10px 16px;"
f"    border-radius: 10px;"
f"    margin: 2px 8px;"
f"    color: {THEME['text']};"
f"    border: none;"
f"}}"
f"QPushButton#categoryBtn:hover {{"
f"    background-color: {THEME['hover']};"
f"}}"
f"QPushButton#categoryBtn:checked {{"
f"    background-color: {THEME['primary']};"
f"    color: {THEME.get('button_text', '#FFFFFF')};"
f"    font-weight: 600;"
f"}}"
f"QLineEdit {{"
f"    background-color: {THEME['surface']};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 8px;"
f"    padding: 8px 12px;"
f"    color: {THEME['text']};"
f"}}"
f"QLineEdit:focus {{"
f"    border: 1px solid {THEME['primary']};"
f"    background-color: {THEME['surface']};"
f"}}"
f"QComboBox {{"
f"    background-color: {THEME['surface']};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 8px;"
f"    padding: 6px 36px 6px 12px;"
f"    color: {THEME['text']};"
f"}}"
f"QComboBox QAbstractItemView {{"
f"    background-color: {_dropdown_bg};"
f"    border: 1px solid {THEME['primary']};"
f"    border-radius: 10px;"
f"    selection-background-color: {THEME['hover']};"
f"    selection-color: {THEME['text']};"
f"    outline: 0;"
f"}}"
f"QComboBoxPrivateContainer {{"
f"    background-color: {_dropdown_bg};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 12px;"
f"    padding: 6px;"
f"}}"
f"QComboBoxPrivateContainer QListView {{"
f"    background-color: {_dropdown_bg};"
f"    border: none;"
f"    outline: 0;"
f"}}"
f"QFrame#qt_combobox_popup {{"
f"    background-color: {_dropdown_bg};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 12px;"
f"}}"
f"QAbstractItemView, QListView {{"
f"    background-color: {_dropdown_bg};"
f"    alternate-background-color: {_dropdown_bg};"
f"    border: 1px solid {THEME['border']};"
f"    selection-background-color: {THEME['hover']};"
f"    selection-color: {THEME['text']};"
f"    outline: 0;"
f"}}"
f"QAbstractItemView::item, QListView::item {{"
f"    color: {THEME['text']};"
f"}}"
f"QAbstractItemView::item:disabled, QListView::item:disabled {{"
f"    color: {THEME.get('text_secondary', THEME['text'])};"
f"}}"
f"QAbstractItemView::item:hover, QListView::item:hover {{"
f"    background-color: {THEME['hover']};"
f"    color: {THEME['text']};"
f"}}"
f"QComboBox QAbstractItemView::item {{"
f"    padding: 8px 12px;"
f"    border-bottom: 1px solid {THEME['border']};"
f"}}"
f"QComboBox QAbstractItemView::item:selected {{"
f"    background-color: {THEME['hover']};"
f"    color: {THEME['text']};"
f"}}"
f"QComboBox::drop-down {{"
f"    subcontrol-origin: padding;"
f"    subcontrol-position: top right;"
f"    width: 32px;"
f"    border-left: 1px solid {THEME['border']};"
f"    background-color: rgba(255, 255, 255, 0.08);"
f"    border-top-right-radius: 8px;"
f"    border-bottom-right-radius: 8px;"
f"}}"
f"QComboBox::down-arrow {{"
f"    width: 14px;"
f"    height: 14px;"
f"    margin-right: 9px;"
f"    background: transparent;"
f"    image: url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24'><path fill='%23E7E7F2' d='M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z'/></svg>\");"
f"}}"
f"QScrollArea {{"
f"    background-color: transparent;"
f"    border: none;"
f"}}"
f"QScrollBar:vertical {{"
f"    border: none;"
f"    background: transparent;"
f"    width: 8px;"
f"    margin: 0;"
f"}}"
f"QScrollBar::handle:vertical {{"
f"    background: {THEME.get('scrollbar', THEME['text_secondary'])};"
f"    border-radius: 4px;"
f"    min-height: 20px;"
f"}}"
f"QScrollBar::handle:vertical:hover {{"
f"    background: {THEME.get('scrollbar_hover', THEME.get('scrollbar', THEME['text_secondary']))};"
f"}}"
f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
f"    height: 0px;"
f"}}"
f"QMenu {{"
f"    background-color: {_dropdown_bg};"
f"    border: 1px solid {THEME['border']};"
f"    color: {THEME['text']};"
f"    padding: 6px;"
f"    border-radius: 12px;"
f"}}"
f"QMenu::item {{"
f"    padding: 8px 24px;"
f"    border-radius: 6px;"
f"    color: {THEME['text']};"
f"}}"
f"QMenu::item:selected {{"
f"    background-color: {THEME['hover']};"
f"    color: {THEME['text']};"
f"}}"
f"QDialog {{"
f"    background: {THEME['background'] if SETTINGS.get('theme') in ('red_blue_glass','custom_image') else THEME['surface']};"
f"    border-radius: 16px;"
f"}}"
f"QDialog#settingsDialog {{"
f"    background: {THEME['background'] if SETTINGS.get('theme') in ('red_blue_glass','custom_image') else THEME['surface']};"
f"    border-radius: 16px;"
f"}}"
f"QDialog#toolDialog {{"
f"    background: {THEME['background'] if SETTINGS.get('theme') in ('red_blue_glass','custom_image') else THEME['surface']};"
f"    border-radius: 16px;"
f"}}"
f"QTabWidget::pane {{"
f"    border: 1px solid {THEME['border']};"
f"    background-color: {THEME['surface']};"
f"    border-radius: 4px;"
f"}}"
f"QTabBar::tab {{"
f"    background-color: {THEME['surface']};"
f"    color: {THEME['text']};"
f"    padding: 8px 20px;"
f"    border: 1px solid {THEME['border']};"
f"    border-bottom: none;"
f"    border-top-left-radius: 6px;"
f"    border-top-right-radius: 6px;"
f"    margin-right: 2px;"
f"}}"
f"QTabBar::tab:selected {{"
f"    color: {THEME['primary']};"
f"    border-bottom: 2px solid {THEME['primary']};"
f"}}"
f"QTabBar::tab:hover:!selected {{"
f"    background-color: {THEME['hover']};"
f"}}"
f"QDialog#settingsDialog QScrollArea {{"
f"    background-color: {THEME['surface']};"
f"    border: none;"
f"}}"
f"QDialog#settingsDialog QLabel {{"
f"    color: {THEME['text']};"
f"    background-color: transparent;"
f"}}"
f"QDialog#settingsDialog QTabWidget::pane {{"
f"    background-color: {THEME['surface']};"
f"    border: 1px solid {THEME['border']};"
f"}}"
f"QDialog#settingsDialog QTabBar::tab {{"
f"    background-color: {THEME['surface']};"
f"    color: {THEME['text']};"
f"    padding: 8px 20px;"
f"    border: 1px solid {THEME['border']};"
f"    border-bottom: none;"
f"    border-top-left-radius: 6px;"
f"    border-top-right-radius: 6px;"
f"}}"
f"QDialog#settingsDialog QTabBar::tab:selected {{"
f"    color: {THEME['primary']};"
f"    border-bottom: 2px solid {THEME['primary']};"
f"}}"
f"QDialog#settingsDialog QTabBar::tab:hover:!selected {{"
f"    background-color: {THEME['hover']};"
f"}}"
f"QDialog#toolDialog QLabel {{"
f"    color: {THEME['text']};"
f"    background-color: transparent;"
f"}}"
f"QDialog#settingsDialog QPushButton, QDialog#toolDialog QPushButton, QMessageBox QPushButton, QDialogButtonBox QPushButton, QPushButton#dialogBtn {{"
f"    background-color: {THEME['primary']};"
f"    color: {THEME.get('button_text', '#FFFFFF')};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 10px;"
f"    padding: 8px 16px;"
f"    font-weight: 600;"
f"}}"
f"QDialog#settingsDialog QPushButton:hover, QDialog#toolDialog QPushButton:hover, QMessageBox QPushButton:hover, QDialogButtonBox QPushButton:hover, QPushButton#dialogBtn:hover {{"
f"    background-color: {THEME['primary']};"
f"    color: {THEME.get('button_text', '#FFFFFF')};"
f"    border: 1px solid {THEME['border']};"
f"}}"
f"QDialog#settingsDialog QPushButton:pressed, QDialog#toolDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QDialogButtonBox QPushButton:pressed, QPushButton#dialogBtn:pressed {{"
f"    background-color: {THEME['primary']};"
f"}}"
f"QMessageBox {{"
f"    background: {THEME['background'] if SETTINGS.get('theme') in ('red_blue_glass','custom_image') else THEME['surface']};"
f"}}"
f"QMessageBox QLabel {{"
f"    color: {THEME['text']};"
f"}}"
f"QGroupBox {{"
f"    color: {THEME['text']};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 8px;"
f"    margin-top: 12px;"
f"    padding-top: 12px;"
f"}}"
f"QGroupBox::title {{"
f"    color: {THEME['text']};"
f"    subcontrol-origin: margin;"
f"    left: 12px;"
f"    padding: 0 6px;"
f"}}"
f"QCheckBox {{"
f"    color: {THEME['text']};"
f"    spacing: 8px;"
f"}}"
f"QCheckBox::indicator {{"
f"    width: 16px; height: 16px;"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 3px;"
f"    background-color: {THEME['surface']};"
f"}}"
f"QCheckBox::indicator:checked {{"
f"    background-color: {THEME['primary']};"
f"    border: 1px solid {THEME['primary']};"
f"}}"
f"QSpinBox {{"
f"    background-color: {THEME['surface']};"
f"    color: {THEME['text']};"
f"    border: 1px solid {THEME['border']};"
f"    border-radius: 6px;"
f"    padding: 4px 8px;"
f"}}"
)

def load_tools ():
    try :
        if os .path .exists (TOOLS_FILE ):
            with open (TOOLS_FILE ,'r',encoding ='utf-8')as f :
                raw =json .load (f )
            base_dir =os .path .dirname (os .path .abspath (__file__ ))
            def _normalize_tool (t ):
                if not isinstance (t ,dict ):
                    return None 
                tool =dict (t )
                key_map ={
                "tool_name":"name",
                "title":"name",
                "tool_title":"name",
                "tool_category":"category",
                "cate":"category",
                "tool_type":"type",
                "env":"type",
                "env_type":"type",
                "tool_path":"path",
                "file":"path",
                "filepath":"path",
                "tool_params":"params",
                "param":"params",
                "args":"params",
                "tool_url":"url",
                "link":"url",
                "tool_desc":"description",
                "desc":"description",
                "priority":"weight",
                "order":"weight",
                }
                for oldk ,newk in key_map .items ():
                    if newk not in tool and oldk in tool :
                        tool [newk ]=tool .get (oldk )

                if "name"not in tool :
                    tool ["name"]=""
                if "category"not in tool :
                    tool ["category"]=""
                if "type"not in tool :
                    tool ["type"]=""
                if "path"not in tool :
                    tool ["path"]=""
                if "params"not in tool :
                    tool ["params"]=""
                if "params_pre"not in tool :
                    tool ["params_pre"]=""
                if "url"not in tool :
                    tool ["url"]=""
                if "description"not in tool :
                    tool ["description"]=""

                try :
                    tool ["weight"]=float (tool .get ("weight",0 )or 0 )
                except Exception :
                    tool ["weight"]=0.0

                tool ["tags"]=[] 

                if "group"not in tool :
                    tool ["group"]=""
                return tool 

            tools =[]
            if isinstance (raw ,list ):
                tools =raw 
            elif isinstance (raw ,dict ):
                if isinstance (raw .get ("tools"),list ):
                    tools =raw .get ("tools")
                elif isinstance (raw .get ("data"),list ):
                    tools =raw .get ("data")
                elif isinstance (raw .get ("items"),list ):
                    tools =raw .get ("items")

            out =[]
            for t in tools :
                tool =_normalize_tool (t )
                if not tool :
                    continue 
                p_original =tool .get ('path','')
                if p_original :
                    p_norm =str (p_original ).replace ('\\','/').strip ()
                    if (
                    p_norm .startswith ('/tools/')or 
                    p_norm .startswith ('\\tools\\')or 
                    p_norm .startswith ('/tools\\')or 
                    p_norm .startswith ('\\tools/')
                    ):
                        rel_part =p_norm .lstrip ('/\\')
                        abs_path =os .path .join (base_dir ,rel_part )
                        tool ['path']=abs_path 
                out .append (tool )
            return out 
    except Exception as e :
        print (f"加载工具数据失败: {e}")
    return []

def save_tools (tools ):
    try :
        os .makedirs (os .path .dirname (TOOLS_FILE ),exist_ok =True )
        base_dir =os .path .dirname (os .path .abspath (__file__ ))
        base_tools_dir =os .path .join (base_dir ,"tools")
        out_list =[]
        for t in tools :
            clone =t .copy ()
            p =clone .get ('path','')
            if not p :
                out_list .append (clone )
                continue
            # 裸命令名（如 nmap / sqlmap）不是文件路径，保持原样，不做绝对化
            if not ("/" in p or "\\" in p or os .path .sep in p ):
                out_list .append (clone )
                continue
            abs_path =os .path .abspath (p )
            try :
                if os .path .commonpath ([
                os .path .normcase (os .path .abspath (abs_path )),
                os .path .normcase (os .path .abspath (base_tools_dir ))
                ])==os .path .normcase (os .path .abspath (base_tools_dir )):
                    rel2base =os .path .relpath (abs_path ,base_dir )
                    clone ['path']="/"+rel2base .replace ("\\","/")
                else :
                    clone ['path']=abs_path
            except (ValueError ,TypeError ):
                clone ['path']=abs_path 
            clone ["tags"]=[]  # 标签功能已禁用
            if "group"not in clone :
                clone ["group"]=""
            out_list .append (clone )
        _atomic_write_json (TOOLS_FILE ,out_list )
        return True
    except Exception as e :
        print (f"保存工具数据失败: {e}")
        return False 

def load_categories ():
    try :
        if not os .path .exists (os .path .join (BASE_DIR ,"config")):
            os .makedirs (os .path .join (BASE_DIR ,"config"),exist_ok =True )
        if not os .path .exists (CATEGORIES_FILE ):
            _atomic_write_json (CATEGORIES_FILE ,{"categories":DEFAULT_CATEGORIES })
            return DEFAULT_CATEGORIES 
        with open (CATEGORIES_FILE ,"r",encoding ="utf-8")as f :
            data =json .load (f )
            if isinstance (data ,dict )and "categories"in data :
                return data ["categories"]
    except Exception as e :
        print (f"加载分类数据出错: {e}")
    return DEFAULT_CATEGORIES 

def save_categories (categories_list ):
    try :
        if not os .path .exists (os .path .join (BASE_DIR ,"config")):
            os .makedirs (os .path .join (BASE_DIR ,"config"),exist_ok =True )
        _atomic_write_json (CATEGORIES_FILE ,{"categories":categories_list })
        return True
    except Exception as e :
        print (f"保存分类数据出错: {e}")
        return False 

def export_all_data (filepath :str ):
    data ={
    "tools":load_tools (),
    "categories":load_categories (),
    "settings":load_settings (),
    }
    if os .path .exists (HOTKEYS_FILE ):
        with open (HOTKEYS_FILE ,"r",encoding ="utf-8")as f :
            data ["hotkeys"]=json .load (f )
    _atomic_write_json (filepath ,data )

def import_all_data (filepath :str ,mode ="merge"):
    with open (filepath ,"r",encoding ="utf-8")as f :
        data =json .load (f )
    if mode =="overwrite":
        if "tools"in data :
            tools =data .get ("tools")
            if isinstance (tools ,list ):
                save_tools (tools )
            elif isinstance (tools ,dict )and isinstance (tools .get ("tools"),list ):
                save_tools (tools .get ("tools"))
        if "categories"in data :
            save_categories (data ["categories"])
        if "settings"in data :
            save_settings (data ["settings"])
        if "hotkeys"in data :
            _atomic_write_json (HOTKEYS_FILE ,data ["hotkeys"])
    else :
        old_tools =load_tools ()
        tool_keys ={(t ['name'],t ['category'])for t in old_tools }
        add_tools =[]
        incoming =data .get ("tools",[])
        if isinstance (incoming ,dict )and isinstance (incoming .get ("tools"),list ):
            incoming =incoming .get ("tools")
        for t in incoming :
            try :
                if (t ['name'],t ['category'])not in tool_keys :
                    add_tools .append (t )
            except Exception :
                continue
        save_tools (old_tools +add_tools )
        old_cats =set (load_categories ())
        new_cats =set (data .get ("categories",[]))
        save_categories (list (old_cats |new_cats ))
        old_set =load_settings ()
        old_set .update (data .get ("settings",{}))
        save_settings (old_set )
        if "hotkeys"in data :
            if os .path .exists (HOTKEYS_FILE ):
                with open (HOTKEYS_FILE ,"r",encoding ="utf-8")as f2 :
                    old_map =json .load (f2 )
            else :
                old_map ={}
            old_map .update (data ["hotkeys"])
            _atomic_write_json (HOTKEYS_FILE ,old_map )
