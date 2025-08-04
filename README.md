# Chaoxing-EdgeProxy

用于超星学习通的边缘代理，通过具有动态 IP 的边缘设备代理访问学习通服务器

<img src="https://github.com/Misaka-1314/Chaoxing-EdgeProxy/raw/refs/heads/main/assets/时序图.png" />
<img src="https://github.com/Misaka-1314/Chaoxing-EdgeProxy/raw/refs/heads/main/assets/结构图.png" />

## 使用方法

POST http://localhost:8000/proxy

```json
{
    "url": "https://www.baidu.com",
    "method": "GET"
}
```

```json
{
    "url": "https://www.baidu.com",
    "method": "POST",
    "headers": {
        "Content-Type": "application/json"
    },
    "cookies": {
        "cookie1": "value1",
        "cookie2": "value2"
    },
    "params": {
        "param1": "value1",
        "param2": "value2"
    },
    "body": "{\"key\": \"value\"}"
}
```