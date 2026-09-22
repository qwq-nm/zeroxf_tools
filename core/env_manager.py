import os 
import sys 
import subprocess 
import json 
import re 
import logging 
from typing import Dict ,Optional ,List 


logging .basicConfig (level =logging .INFO ,format ='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger =logging .getLogger ("EnvManager")

# 可执行文件扩展名（Windows 为 .exe，类 Unix 为空）
_EXE =".exe"if os .name =="nt"else ""

class EnvManager :
    _instance =None 

    def __new__ (cls ):
        if cls ._instance is None :
            cls ._instance =super (EnvManager ,cls ).__new__ (cls )
            cls ._instance .init ()
        return cls ._instance 

    def init (self ):

        self .base_dir =os .path .dirname (os .path .dirname (os .path .abspath (__file__ )))
        self .settings_file =os .path .join (self .base_dir ,"config","settings.json")


        self .python_builtin =os .path .join (self .base_dir ,"python3")
        self .java_root =os .path .join (self .base_dir ,"Java_path")
        self .java8_builtin =os .path .join (self .java_root ,"Java_8_win")
        self .java11_builtin =os .path .join (self .java_root ,"Java_11_win")

    def _resolve_path (self ,p :str )->str :
        try :
            p =str (p or "").strip ()
        except Exception :
            return ""

        if not p :
            return ""

        try :
            if os .path .isabs (p ):
                return p 
        except Exception :
            pass 

        try :
            return os .path .normpath (os .path .join (self .base_dir ,p ))
        except Exception :
            return p 

    def _get_settings (self )->dict :
        if os .path .exists (self .settings_file ):
            try :
                with open (self .settings_file ,'r',encoding ='utf-8')as f :
                    return json .load (f )
            except Exception as e :
                logger .error (f"读取配置失败: {e}")
        return {}

    def _find_cli_interpreter (self ,interp_type :str ,name :str )->Optional [dict ]:
        settings =self ._get_settings ()
        if interp_type =="python":
            arr =settings .get ("cli_python_interpreters",[])
        elif interp_type =="java":
            arr =settings .get ("cli_java_interpreters",[])
        else :
            return None 
        for item in arr :
            try :
                if item .get ("name")==name :
                    return item 
            except Exception :
                continue 
        return None 

    def get_python_path (self )->str :
        settings =self ._get_settings ()
        custom =self ._resolve_path (settings .get ("python_path",""))
        if custom and os .path .exists (custom ):
            return custom 


        builtin_exe =os .path .join (self .python_builtin ,"python.exe")
        if os .path .exists (builtin_exe ):
            return builtin_exe 


        return "python"

    def get_java_home (self ,version ="8")->str :

        settings =self ._get_settings ()
        key ="java8_path"if version =="8"else "java11_path"
        custom =self ._resolve_path (settings .get (key ,""))

        if custom and os .path .exists (custom ):

            if os .path .basename (custom ).lower ()=="bin":
                return os .path .dirname (custom )
            return custom 


        target =self .java8_builtin if version =="8"else self .java11_builtin 

        if os .path .exists (os .path .join (target ,"bin","java"+_EXE )):
            return target

        return ""

    def get_java_exe (self ,version ="8",gui =False )->str :
        home =self .get_java_home (version )
        if not home :
            return "javaw"if gui else "java"

        exe_name =("javaw"if gui else "java")+_EXE
        exe_path =os .path .join (home ,"bin",exe_name )
        if os .path .exists (exe_path ):
            return exe_path 
        return exe_name 

    def get_injected_env (self ,env_type ="all")->Dict [str ,str ]:
        env =os .environ .copy ()
        new_paths =[]

        cli_py =None 
        cli_java =None 


        try :
            if isinstance (env_type ,str )and env_type .startswith ("Python(")and env_type .endswith (")"):
                name =env_type [7 :-1 ]
                item =self ._find_cli_interpreter ("python",name )
                if item :
                    p =self ._resolve_path (item .get ("path",""))
                    if p and os .path .exists (p ):
                        cli_py =p 
                env_type ="python"
            elif isinstance (env_type ,str )and env_type .startswith ("Java(")and env_type .endswith (")"):
                name =env_type [5 :-1 ]
                item =self ._find_cli_interpreter ("java",name )
                if item :
                    p =self ._resolve_path (item .get ("path",""))
                    if p :
                        cli_java =p 
                env_type ="java"
        except Exception :
            pass 

        if env_type in ["python","all"]:
            py_exe =cli_py or self .get_python_path ()

            if os .path .exists (py_exe )and os .path .isfile (py_exe ):
                py_root =os .path .dirname (py_exe )
                py_scripts =os .path .join (py_root ,"Scripts")


                if os .path .exists (py_scripts ):
                    new_paths .append (py_scripts )
                new_paths .append (py_root )

                env ["PYTHONHOME"]=py_root 
                if "PYTHONPATH"in env :
                    del env ["PYTHONPATH"]


        if env_type in ["java","all"]or str (env_type ).lower ().startswith ("java"):
            if cli_java :
                bin_path =os .path .join (cli_java ,"bin")
                if os .path .exists (bin_path ):
                    new_paths .append (bin_path )
                env ["JAVA_HOME"]=cli_java 
            else :

                target_versions =[]
                if "11"in str (env_type ):
                    target_versions =["11","8"]
                else :
                    target_versions =["8","11"]

                for v in target_versions :
                    jhome =self .get_java_home (v )
                    if jhome :
                        bin_path =os .path .join (jhome ,"bin")
                        if os .path .exists (bin_path ):
                            new_paths .append (bin_path )

                        if v in str (env_type )or env_type =="all":
                            if "11"in str (env_type )and v =="11":
                                env ["JAVA_HOME"]=jhome 
                            elif "8"in str (env_type )and v =="8":
                                env ["JAVA_HOME"]=jhome 
                            elif env_type =="all"and v =="8":
                                env ["JAVA_HOME"]=jhome 


            if "JAVA_HOME"in env :
                jh =env ["JAVA_HOME"]
                if os .name =="nt":
                    env ["CLASSPATH"]=f".;{jh}\\lib;{jh}\\lib\\dt.jar;{jh}\\lib\\tools.jar"
                else :
                    env ["CLASSPATH"]=f".:{jh}/lib:{jh}/lib/dt.jar:{jh}/lib/tools.jar"

            # WSLg 会同时暴露 Wayland 和 XWayland。存在 WAYLAND_DISPLAY 时 GDK 默认选
            # Wayland 后端，而 JavaFX 的 GTK 集成在纯 Wayland 下会触发
            # "GDK_IS_X11_DISPLAY (display) failed" 断言并段错误（窗口都还没出来）。
            # 强制 X11 后端，GUI 类 jar 工具（哥斯拉/冰蝎/shiro 等）才能正常显示。
            if os .name !="nt"and env .get ("DISPLAY")and os .environ .get ("WAYLAND_DISPLAY"):
                env .setdefault ("GDK_BACKEND","x11")

        if new_paths :
            original_path =env .get ("PATH","")

            unique_paths =[]
            seen =set ()
            for p in new_paths :
                norm =os .path .normcase (os .path .abspath (p ))
                if norm not in seen :
                    unique_paths .append (p )
                    seen .add (norm )

            env ["PATH"]=os .pathsep .join (unique_paths )+os .pathsep +original_path 

        return env 

    def identify_version (self ,path :str )->str :
        if not path or not os .path .exists (path ):
            return "未找到"

        try :
            filename =os .path .basename (path ).lower ()
            if "java"in filename :

                res =subprocess .run ([path ,"-version"],stderr =subprocess .PIPE ,stdout =subprocess .PIPE ,text =True ,creationflags =subprocess .CREATE_NO_WINDOW if sys .platform =='win32'else 0 )
                output =res .stderr +res .stdout 
                match =re .search (r'version "(.*?)"',output )
                if match :
                    return match .group (1 )

                match =re .search (r'(\d+(\.\d+)+)',output )
                if match :
                    return match .group (1 )
            elif "python"in filename :
                res =subprocess .run ([path ,"--version"],stdout =subprocess .PIPE ,stderr =subprocess .PIPE ,text =True ,creationflags =subprocess .CREATE_NO_WINDOW if sys .platform =='win32'else 0 )
                output =res .stdout +res .stderr 
                return output .strip ().split (" ")[-1 ]
        except Exception as e :
            return f"识别错误: {e}"
        return "未知版本"

    def run_tool_command (self ,cmd_str :str ,cwd :str ,env_type ="all",block =False ):
        env =self .get_injected_env (env_type )
        if block :
            subprocess .call (cmd_str ,shell =True ,cwd =cwd ,env =env )
        else :
            subprocess .Popen (cmd_str ,shell =True ,cwd =cwd ,env =env )
