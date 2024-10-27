import asyncio

async def relay(reader, writer):
    """简单的数据转发函数"""
    try:
        while True:
            data = await reader.read(4096)
            print(data)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()

async def handle_client(local_reader, local_writer):
    # 读取 CONNECT 请求头
    header = await local_reader.readline()
    request_line = header.decode(errors='ignore')
    method, path, protocol = request_line.split()

    # 确保这是一个 CONNECT 请求
    if method != 'CONNECT':
        print("非 CONNECT 方法")
        local_writer.close()
        return

    # 这里你可以解析出真实要请求的 host 和 port（例如 "api.openai.com:443"）
    host, port = path.split(':')

    # 为了简化示例，我们直接连接到目标服务器
    # 在实际应用中，你可能需要修改这里，将请求转发到其他地址或做其他处理
    target_reader, target_writer = await asyncio.open_connection(host, int(port))

    # 响应 CONNECT 请求，表示隧道已建立
    local_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
    await local_writer.drain()

    # 开始转发数据
    task_to_local = asyncio.create_task(relay(target_reader, local_writer))
    task_to_remote = asyncio.create_task(relay(local_reader, target_writer))

    # 等待双向转发结束
    await asyncio.wait([task_to_local, task_to_remote], return_when=asyncio.FIRST_COMPLETED)

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 25735)
    async with server:
        await server.serve_forever()

asyncio.run(main())
