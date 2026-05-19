# test_deepresearch.py
# 目的：测试 deepresearch 项目的核心功能（不依赖 UI）
# 层次：Core + Adapter + Storage
# 使用方法：python test_deepresearch.py

import asyncio
from app.core.conversation_service import ConversationService
from app.core.context_service import ContextService
from app.adapters.file_parsers import parse_file  # 假设 parse_file 是统一接口
from app.storage.conversation_repo import ConversationRepo
from app.config import model_type  # 读取全局配置

async def test_send_message():
    print("=== 测试 Core: send_message ===")
    conv_service = ConversationService()
    ctx_service = ContextService()

    session_id = "test_session"
    text = "你好，测试消息"
    model = model_type  # 从配置读取

    result = await conv_service.send_message(
        session_id=session_id,
        text=text,
        model_type=model,
        thinking=True
    )

    print("发送消息返回：", result)
    assert "content" in result, "消息返回缺少 content 字段"

async def test_file_parsing():
    print("=== 测试 Adapters: 文件解析 ===")
    test_file_txt = "./test_files/sample.txt"  # 你可以准备一个测试文件
    content = parse_file(test_file_txt)
    print("解析内容：", content)
    assert len(content) > 0, "解析结果为空"

async def test_context_building():
    print("=== 测试 Core: 上下文构建 ===")
    ctx_service = ContextService()
    messages = [
        {"role": "user", "content": "第一条消息"},
        {"role": "assistant", "content": "第一条回复"}
    ]
    context = ctx_service.build_context(messages)
    print("拼接上下文：", context)
    assert "第一条消息" in context, "上下文缺少消息内容"

async def test_storage_repo():
    print("=== 测试 Storage: conversation_repo ===")
    repo = ConversationRepo()
    session_id = "test_storage"
    text = "存储测试消息"
    repo.save_message(session_id=session_id, text=text, role="user")
    loaded = repo.load_messages(session_id=session_id)
    print("读取消息：", loaded)
    assert any(m["content"] == text for m in loaded), "存储或读取失败"

async def main():
    await test_send_message()
    await test_file_parsing()
    await test_context_building()
    await test_storage_repo()
    print("=== 所有测试完成 ===")

if __name__ == "__main__":
    asyncio.run(main())