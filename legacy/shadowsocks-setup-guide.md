# Shadowsocks-libev 安装和配置指南

## 📋 目录
- [服务器端安装](#服务器端安装)
- [配置文件](#配置文件)
- [服务管理](#服务管理)
- [ECS 端口开放](#ecs-端口开放)
- [客户端配置](#客户端配置)

---

## 🖥️ 服务器端安装

### 1. 安装依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y shadowsocks-libev
```

### 2. 检查安装状态

```bash
# 检查服务状态
sudo systemctl status shadowsocks-libev

# 查看版本
ss-server -v
```

---

## ⚙️ 配置文件

### 配置文件位置
```
/etc/shadowsocks-libev/config.json
```

### 当前配置内容
```json
{
  "server": "0.0.0.0",
  "server_port": 23333,
  "password": "luobo2024",
  "method": "aes-256-gcm",
  "timeout": 300,
  "fast_open": true,
  "reuse_port": true
}
```

### 配置说明

| 参数 | 说明 | 当前值 |
|------|------|--------|
| `server` | 监听地址 | `0.0.0.0`（所有网卡） |
| `server_port` | 监听端口 | `23333` |
| `password` | 连接密码 | `luobo2024` |
| `method` | 加密方式 | `aes-256-gcm` |
| `timeout` | 超时时间 | `300` 秒 |
| `fast_open` | TCP Fast Open | `true` |
| `reuse_port` | 端口复用 | `true` |

### 推荐的加密方式

```bash
# 性能优先（推荐）
aes-256-gcm
aes-128-gcm
chacha20-ietf-poly1305

# 兼容性优先
aes-256-cfb
aes-128-cfb
```

### 修改配置

```bash
# 编辑配置文件
sudo vim /etc/shadowsocks-libev/config.json

# 修改后重启服务
sudo systemctl restart shadowsocks-libev
```

---

## 🔧 服务管理

### 启动/停止/重启

```bash
# 启动
sudo systemctl start shadowsocks-libev

# 停止
sudo systemctl stop shadowsocks-libev

# 重启
sudo systemctl restart shadowsocks-libev

# 开机自启
sudo systemctl enable shadowsocks-libev

# 禁用开机自启
sudo systemctl disable shadowsocks-libev
```

### 检查状态

```bash
# 查看服务状态
sudo systemctl status shadowsocks-libev

# 查看日志
sudo journalctl -u shadowsocks-libev -f

# 检查端口监听
sudo ss -tuln | grep 23333
```

---

## 🌐 ECS 端口开放

### 1. 服务器防火墙（iptables/ufw）

#### 使用 ufw（推荐）

```bash
# 检查 ufw 状态
sudo ufw status

# 开放端口
sudo ufw allow 23333/tcp
sudo ufw allow 23333/udp

# 重新加载
sudo ufw reload

# 查看规则
sudo ufw status numbered
```

#### 使用 iptables

```bash
# 开放 TCP 端口
sudo iptables -A INPUT -p tcp --dport 23333 -j ACCEPT

# 开放 UDP 端口
sudo iptables -A INPUT -p udp --dport 23333 -j ACCEPT

# 保存规则
sudo iptables-save > /etc/iptables/rules.v4

# 查看规则
sudo iptables -L -n | grep 23333
```

### 2. 腾讯云安全组（重要！）

**步骤**：

1. **登录腾讯云控制台**
   - https://console.cloud.tencent.com/

2. **进入云服务器 CVM**
   - 找到你的服务器实例

3. **配置安全组**
   - 点击实例 ID → 安全组 → 编辑规则
   - 或直接访问：https://console.cloud.tencent.com/cvm/securitygroup

4. **添加入站规则**

   | 协议 | 端口 | 来源 | 策略 | 备注 |
   |------|------|------|------|------|
   | TCP | 23333 | 0.0.0.0/0 | 允许 | Shadowsocks TCP |
   | UDP | 23333 | 0.0.0.0/0 | 允许 | Shadowsocks UDP |

5. **保存规则**
   - 点击"完成"或"保存"

**安全组截图示例**：
```
入站规则：
+--------+-------+------------+------+------------------+
| 协议   | 端口  | 来源       | 策略 | 备注             |
+--------+-------+------------+------+------------------+
| TCP    | 22    | 0.0.0.0/0  | 允许 | SSH              |
| TCP    | 23333 | 0.0.0.0/0  | 允许 | Shadowsocks TCP  |
| UDP    | 23333 | 0.0.0.0/0  | 允许 | Shadowsocks UDP  |
+--------+-------+------------+------+------------------+
```

---

## 📱 客户端配置

### 通用配置信息

```
服务器地址：43.155.155.56
服务器端口：23333
密码：luobo2024
加密方式：aes-256-gcm
```

### Windows 客户端

**推荐软件**：Shadowsocks-Windows

**下载地址**：
- https://github.com/shadowsocks/shadowsocks-windows/releases

**配置步骤**：
1. 下载并解压 `Shadowsocks.exe`
2. 右键托盘图标 → 服务器 → 编辑服务器
3. 填入配置信息
4. 右键 → 启用系统代理

### macOS 客户端

**推荐软件**：ShadowsocksX-NG

**下载地址**：
- https://github.com/shadowsocks/ShadowsocksX-NG/releases

**配置步骤**：
1. 下载并安装 `.dmg` 文件
2. 打开应用 → 服务器设置
3. 填入配置信息
4. 点击"打开 Shadowsocks"

### iOS 客户端

**推荐软件**：Potatso / Shadowrocket

**配置步骤**：
1. App Store 购买/下载
2. 添加节点 → 手动配置
3. 填入服务器信息
4. 连接

### Android 客户端

**推荐软件**：Shadowsocks for Android

**下载地址**：
- Google Play: Shadowsocks
- GitHub: https://github.com/shadowsocks/shadowsocks-android/releases

**配置步骤**：
1. 安装 APK
2. 点击右上角 "+" → 手动设置
3. 填入服务器信息
4. 点击连接按钮

---

## ✅ 测试连接

### 1. 检查服务器端口

```bash
# 在服务器上检查
sudo ss -tuln | grep 23333

# 预期输出
tcp   LISTEN 0      1024         0.0.0.0:23333      0.0.0.0:*
```

### 2. 从客户端测试

```bash
# 使用 telnet 测试
telnet 43.155.155.56 23333

# 使用 nc 测试
nc -zv 43.155.155.56 23333
```

### 3. 测试代理

```bash
# 使用 curl 测试（通过代理）
curl --socks5 127.0.0.1:1080 http://ipinfo.io

# 预期输出
{
  "ip": "43.155.155.56",
  "city": "Seoul",
  "country": "KR",
  ...
}
```

---

## 🔒 安全建议

### 1. 修改默认端口

```json
{
  "server_port": 8388  // 改成非常见端口
}
```

### 2. 使用强密码

```bash
# 生成随机密码
openssl rand -base64 16
```

### 3. 限制访问 IP（可选）

**在安全组中**：
- 来源改为你的 IP 地址，而不是 `0.0.0.0/0`

### 4. 启用 TCP Fast Open

```bash
# 检查是否启用
cat /proc/sys/net/ipv4/tcp_fastopen

# 临时启用
echo 3 > /proc/sys/net/ipv4/tcp_fastopen

# 永久启用
echo "net.ipv4.tcp_fastopen = 3" >> /etc/sysctl.conf
sudo sysctl -p
```

---

## 🐛 常见问题

### 1. 连接超时

**原因**：
- 防火墙未开放端口
- 安全组未配置
- 服务未启动

**解决**：
```bash
# 检查服务状态
sudo systemctl status shadowsocks-libev

# 检查端口
sudo ss -tuln | grep 23333

# 检查防火墙
sudo ufw status
```

### 2. 认证失败

**原因**：
- 密码错误
- 加密方式不匹配

**解决**：
- 检查客户端和服务器配置是否一致

### 3. 速度慢

**原因**：
- 加密方式太复杂
- 服务器带宽不足

**解决**：
- 使用 `aes-128-gcm` 或 `chacha20-ietf-poly1305`
- 检查服务器带宽

---

## 📊 性能优化

### 1. 优化内核参数

```bash
# 编辑 /etc/sysctl.conf
sudo vim /etc/sysctl.conf

# 添加以下内容
fs.file-max = 51200
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq

# 应用配置
sudo sysctl -p
```

### 2. 启用 BBR

```bash
# 检查 BBR 是否启用
lsmod | grep bbr

# 如果未启用
echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
sudo sysctl -p
```

---

## 📝 配置清单

- ✅ Shadowsocks-libev 已安装
- ✅ 服务已启动（端口 23333）
- ✅ 服务器防火墙已开放端口
- ✅ 腾讯云安全组已配置
- ✅ 客户端配置完成

---

## 📞 快速配置信息

```
服务器：43.155.155.56
端口：23333
密码：luobo2024
加密：aes-256-gcm
```

**配置文件路径**：`/etc/shadowsocks-libev/config.json`

**服务管理命令**：
```bash
sudo systemctl restart shadowsocks-libev  # 重启
sudo systemctl status shadowsocks-libev   # 状态
```

---

**生成时间**：2026-03-17
**文档维护**：首尔虾（OpenClaw AI Agent）
