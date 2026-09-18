import sys 
import os 
import math 
import time 
import random 
import threading 
import subprocess 
import ctypes 
from PyQt6 .QtWidgets import QApplication ,QWidget 
from PyQt6 .QtCore import Qt ,QTimer ,QPointF ,QRectF 
from PyQt6 .QtGui import (
QPainter ,QColor ,QPen ,QFont ,QPainterPath ,QIcon ,
QRadialGradient ,QLinearGradient ,QPixmap ,QBrush 
)


try :
    from config import load_tools 
except ImportError :
    load_tools =lambda :[]

PRELOADED_DATA ={}

def preload_main_py ():
    try :
        import importlib 
        importlib .import_module ("main")
        print ("main.py 预加载完成")
    except Exception as e :
        print (f"预加载 main.py 异常: {e}")

class FluidParticle :
    def __init__ (self ,w ,h ,center_x ,center_y ):
        self .reset (w ,h ,center_x ,center_y ,first =True )

    def reset (self ,w ,h ,center_x ,center_y ,first =False ):
        angle =random .uniform (0 ,6.28318 )

        base_r =min (w ,h )*0.33 
        if first :
            r =random .uniform (base_r *0.15 ,base_r *1.0 )
        else :
            r =random .uniform (base_r *0.6 ,base_r *1.25 )

        self .theta =angle 
        self .radius =r 
        self .radius_target =r 
        self .omega =random .uniform (-0.035 ,0.035 )
        self .radial_speed =random .uniform (0.002 ,0.008 )

        self .x =center_x +math .cos (self .theta )*self .radius 
        self .y =center_y +math .sin (self .theta )*self .radius 

        self .vx =0.0 
        self .vy =0.0 
        self .size =random .uniform (1.6 ,4.2 )
        self .trail =[]
        self .max_trail =int (random .uniform (8 ,16 ))


        colors_blue =[
        QColor (210 ,245 ,255 ,160 ),
        QColor (140 ,210 ,255 ,150 ),
        QColor (0 ,160 ,255 ,140 ),
        QColor (0 ,210 ,255 ,130 ),
        ]
        colors_red =[
        QColor (255 ,210 ,220 ,155 ),
        QColor (255 ,140 ,160 ,145 ),
        QColor (255 ,80 ,110 ,135 ),
        QColor (255 ,60 ,90 ,125 ),
        ]
        colors_white =[
        QColor (255 ,255 ,255 ,165 ),
        ]

        camp =random .random ()
        if camp <0.45 :
            self .color =random .choice (colors_red )
        elif camp <0.90 :
            self .color =random .choice (colors_blue )
        else :
            self .color =random .choice (colors_white )

        self .phase =random .uniform (0.0 ,6.28318 )
        self .wobble =random .uniform (0.6 ,1.4 )

    def update (self ,center_x ,center_y ):
        self .trail .append ((self .x ,self .y ))
        if len (self .trail )>self .max_trail :
            self .trail .pop (0 )

        self .phase +=0.04 *self .wobble 
        self .theta +=self .omega 

        wob =1.0 +0.08 *math .sin (self .phase )
        self .radius_target *=0.995 
        self .radius_target =max (24.0 ,self .radius_target )
        self .radius +=(self .radius_target -self .radius )*self .radial_speed 

        tx =center_x +math .cos (self .theta )*self .radius *wob 
        ty =center_y +math .sin (self .theta )*self .radius *wob 

        ax =(tx -self .x )*0.12 
        ay =(ty -self .y )*0.12 

        self .vx =(self .vx +ax )*0.86 
        self .vy =(self .vy +ay )*0.86 

        self .x +=self .vx 
        self .y +=self .vy 

        if self .radius <=26.0 :
            return False 

        return True 

class FluidLoader (QWidget ):
    def __init__ (self ):
        super ().__init__ ()
        try :
            ctypes .windll .shcore .SetProcessDpiAwareness (2 )
        except Exception :
            try :
                ctypes .windll .shcore .SetProcessDpiAwareness (1 )
            except Exception :
                pass
            pass 

        self .setWindowFlags (Qt .WindowType .FramelessWindowHint |Qt .WindowType .WindowStaysOnTopHint |Qt .WindowType .Tool )
        self .setAttribute (Qt .WidgetAttribute .WA_TranslucentBackground )

        screen =QApplication .primaryScreen ().geometry ()
        self .size_w =580 
        self .size_h =380 
        self .setGeometry (
        (screen .width ()-self .size_w )//2 ,
        (screen .height ()-self .size_h )//2 ,
        self .size_w ,
        self .size_h 
        )

        self .start_time =time .time ()
        self .duration =2.0 
        self .particles =[]
        for _ in range (140 ):
            self .particles .append (FluidParticle (self .size_w ,self .size_h ,self .size_w /2 ,self .size_h /2 ))

        self .preload_thread =threading .Thread (target =preload_main_py ,daemon =True )
        self .preload_thread .start ()

        base_dir =os .path .dirname (os .path .abspath (__file__ ))
        self .logo_pixmap =QPixmap (os .path .join (base_dir ,"config","fox.png"))
        if self .logo_pixmap .isNull ():
            self .logo_pixmap =None 

        self .timer =QTimer ()
        self .timer .timeout .connect (self .update_animation )
        self .timer .start (16 )

        self .opacity_val =0.0 
        self .logo_scale =0.86 
        self .bg_angle =0 
        self ._t =0.0 

        self .show ()

    def update_animation (self ):
        self .update ()

        elapsed =time .time ()-self .start_time 
        self ._t =elapsed 
        center_x =self .size_w /2 
        center_y =self .size_h /2 

        active_particles =[]
        for p in self .particles :
            if p .update (center_x ,center_y ):
                active_particles .append (p )
            else :
                if elapsed <self .duration -0.8 :
                    p .reset (self .size_w ,self .size_h ,center_x ,center_y )
                    active_particles .append (p )
        self .particles =active_particles 


        fade =0.35 
        if elapsed <fade :
            self .opacity_val =min (1.0 ,elapsed /fade )
        elif elapsed >self .duration -fade :
            self .opacity_val =max (0.0 ,(self .duration -elapsed )/fade )
            self .logo_scale +=0.012 
        else :
            self .opacity_val =1.0 

            self .logo_scale =1.0 +0.03 *math .sin (elapsed *2.5 )

        self .bg_angle +=1 
        if self .bg_angle >=360 :
            self .bg_angle =0 

        if elapsed >=self .duration :
            self .finish ()

    def paintEvent (self ,event ):
        painter =QPainter (self )
        painter .setRenderHint (QPainter .RenderHint .Antialiasing )

        center_x =self .size_w /2 
        center_y =self .size_h /2 

        painter .setOpacity (self .opacity_val )

        orb_r =112 *self .logo_scale 
        orb =QRadialGradient (center_x -18 ,center_y -22 ,orb_r *1.2 )
        orb .setColorAt (0.0 ,QColor (255 ,255 ,255 ,185 ))
        orb .setColorAt (0.35 ,QColor (235 ,250 ,255 ,90 ))
        orb .setColorAt (0.72 ,QColor (170 ,220 ,255 ,55 ))
        orb .setColorAt (1.0 ,QColor (255 ,255 ,255 ,10 ))
        painter .setPen (Qt .PenStyle .NoPen )
        painter .setBrush (QBrush (orb ))
        painter .drawEllipse (QPointF (center_x ,center_y ),orb_r ,orb_r )

        sweep =QLinearGradient (
        QPointF (center_x -orb_r ,center_y -orb_r ),
        QPointF (center_x +orb_r ,center_y +orb_r ),
        )
        ph =(math .sin (self ._t *1.35 )+1.0 )*0.5 
        sweep .setColorAt (max (0.0 ,ph -0.25 ),QColor (255 ,255 ,255 ,0 ))
        sweep .setColorAt (ph ,QColor (255 ,255 ,255 ,95 ))
        sweep .setColorAt (min (1.0 ,ph +0.25 ),QColor (255 ,255 ,255 ,0 ))
        painter .setBrush (QBrush (sweep ))
        painter .setOpacity (self .opacity_val *0.45 )
        painter .drawEllipse (QPointF (center_x ,center_y ),orb_r *0.95 ,orb_r *0.95 )
        painter .setOpacity (self .opacity_val )

        for p in self .particles :
            if len (p .trail )>2 :
                path =QPainterPath ()
                path .moveTo (p .trail [0 ][0 ],p .trail [0 ][1 ])
                for point in p .trail [1 :]:
                    path .lineTo (point [0 ],point [1 ])
                path .lineTo (p .x ,p .y )

                c =QColor (p .color )
                pen =QPen (c ,max (1.2 ,p .size *0.9 ))
                pen .setCapStyle (Qt .PenCapStyle .RoundCap )
                painter .setPen (pen )
                painter .drawPath (path )

            glow =QRadialGradient (p .x ,p .y ,p .size *6.0 )
            cc =QColor (p .color )
            glow .setColorAt (0.0 ,QColor (cc .red (),cc .green (),cc .blue (),130 ))
            glow .setColorAt (0.35 ,QColor (cc .red (),cc .green (),cc .blue (),55 ))
            glow .setColorAt (1.0 ,QColor (cc .red (),cc .green (),cc .blue (),0 ))
            painter .setPen (Qt .PenStyle .NoPen )
            painter .setBrush (QBrush (glow ))
            painter .drawEllipse (QPointF (p .x ,p .y ),p .size *3.2 ,p .size *3.2 )

            painter .setBrush (p .color )
            painter .drawEllipse (QPointF (p .x ,p .y ),p .size ,p .size )

        ring_r =132 *self .logo_scale 
        ring =QRadialGradient (center_x ,center_y ,ring_r )
        ring .setColorAt (0.0 ,QColor (0 ,122 ,255 ,int (40 *self .opacity_val )))
        ring .setColorAt (0.75 ,QColor (0 ,180 ,255 ,int (28 *self .opacity_val )))
        ring .setColorAt (1.0 ,QColor (0 ,122 ,255 ,0 ))
        painter .setBrush (QBrush (ring ))
        painter .setPen (Qt .PenStyle .NoPen )
        painter .drawEllipse (QPointF (center_x ,center_y ),ring_r ,ring_r )


        title_text ="zeroxf 工具箱 V4.0"
        title_rect =QRectF (0 ,center_y +70 ,self .size_w ,32 )
        title_font =QFont ("Microsoft YaHei UI",14 ,QFont .Weight .Bold )
        painter .setFont (title_font )

        grad =QLinearGradient (title_rect .topLeft (),title_rect .topRight ())
        grad .setColorAt (0.0 ,QColor (0 ,210 ,255 ,int (220 *self .opacity_val )))
        grad .setColorAt (0.5 ,QColor (255 ,255 ,255 ,int (240 *self .opacity_val )))
        grad .setColorAt (1.0 ,QColor (0 ,122 ,255 ,int (220 *self .opacity_val )))


        painter .setPen (QColor (0 ,160 ,255 ,int (70 *self .opacity_val )))
        painter .drawText (
        title_rect .translated (0 ,1 ),
        Qt .AlignmentFlag .AlignHCenter |Qt .AlignmentFlag .AlignVCenter ,
        title_text ,
        )

        painter .setPen (QPen (QBrush (grad ),1 ))
        painter .drawText (
        title_rect ,
        Qt .AlignmentFlag .AlignHCenter |Qt .AlignmentFlag .AlignVCenter ,
        title_text ,
        )


        painter .setOpacity (self .opacity_val )

        if self .logo_pixmap :
            s =92 *self .logo_scale 
            target_rect =QRectF (center_x -s /2 ,center_y -s /2 ,s ,s )
            painter .drawPixmap (target_rect .toRect (),self .logo_pixmap )
        else :
            painter .setPen (QColor (255 ,255 ,255 ))
            font =QFont ("Microsoft YaHei UI",int (36 *self .logo_scale ),QFont .Weight .Bold )
            painter .setFont (font )
            painter .drawText (QRectF (0 ,0 ,self .size_w ,self .size_h ),Qt .AlignmentFlag .AlignCenter ,"zeroxf")


        painter .setOpacity (self .opacity_val *0.92 )
        font_small =QFont ("Segoe UI",10 )
        font_small .setLetterSpacing (QFont .SpacingType .AbsoluteSpacing ,3 )
        painter .setFont (font_small )
        painter .setPen (QColor (220 ,240 ,255 ))
        dots =int (((math .sin (self ._t *3.2 )+1.0 )*0.5 )*3 )
        painter .drawText (
        QRectF (0 ,center_y +98 ,self .size_w ,30 ),
        Qt .AlignmentFlag .AlignCenter ,
        "SYSTEM INITIALIZING"+("."*dots ),
        )

    def finish (self ):
        self .timer .stop ()
        self .close ()

        current_dir =os .path .dirname (os .path .abspath (__file__ ))


        try :
            from core .env_manager import EnvManager 
            py_exe =EnvManager ().get_python_path ()
        except :
            py_exe =sys .executable 


        subprocess .Popen ([py_exe ,"main.py"],cwd =current_dir )


        try :
            QApplication .quit ()
        except Exception :
            pass 
        os ._exit (0 )

if __name__ =="__main__":
    app =QApplication (sys .argv )
    loader =FluidLoader ()
    sys .exit (app .exec ())
