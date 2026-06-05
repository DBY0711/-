#!/bin/bash
# RPA 调度可视化 — 阿里云 Ubuntu 22.04 一键部署
set -e

echo "=== 安装依赖 ==="
apt update -qq
apt install -y python3-pip python3-venv nginx git

echo "=== 拉取代码 ==="
cd /opt
if [ -d rpa-schedule ]; then
  cd rpa-schedule && git pull origin main
else
  git clone git@github.com:DBY0711/-.git rpa-schedule
  cd rpa-schedule
fi

echo "=== Python 隔离环境 ==="
python3 -m venv .venv
.venv/bin/pip install flask gunicorn

echo "=== systemd 服务 ==="
cat > /etc/systemd/system/rpa-schedule.service << 'SVC'
[Unit]
Description=RPA Schedule App
After=network.target

[Service]
User=root
WorkingDirectory=/opt/rpa-schedule
ExecStart=/opt/rpa-schedule/.venv/bin/python /opt/rpa-schedule/server.py
Restart=always

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable rpa-schedule
systemctl restart rpa-schedule

echo "=== Nginx 反代 ==="
cat > /etc/nginx/sites-enabled/rpa-schedule << 'NGX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGX

rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== 完成 ==="
echo "访问: http://$(curl -s ifconfig.me)"
