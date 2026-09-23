import json
from typing import Any
from pathlib import Path
from src.bootstrap import build_agent_controller


def read_json(file_path: str | Path) -> Any:
    """Đọc file JSON và trả về object Python."""
    path = Path(file_path)

    with path.open(
            mode="r",
            encoding="utf-8"
    ) as file:
        return json.load(file)


def write_json(
        file_path: str | Path,
        data: Any,
        indent: int = 4
) -> None:
    """Ghi object Python thành file JSON."""
    with file_path.open(
            mode="w",
            encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=indent
        )


def read_history(history_path: Path):
    if not history_path.exists():
        return None
    return read_json(history_path)


def write_history(history_path: Path, data):
    write_json(
        data=data,
        file_path=history_path
    )


def main():
    from src.config import Config

    history_path = Config.DATA / 'agent_history.json'

    controller = build_agent_controller()
    '''Lấy Agent controller từ bootstrap'''

    system_prompt = '''You are an autonomous AI src operating in a local workspace.
Your goal is to help the user research, analyze, and process information using available tools.
Core rules:
1. Use tools instead of guessing.
2. The workspace is your long-term memory. Conversation context is temporary.
3. Before reading files:
   - Discover files first.
   - Check file information before reading large files.
   - Never load large documents completely unless necessary.
4. For large documents:
   - Search relevant sections.
   - Read only required parts.
   - Process incrementally.
5. Save important results into workspace files instead of keeping everything in chat.
6. Prefer structured outputs (json, md) for reusable information.
7. Never access files outside workspace.
8. Never claim information you have not retrieved.
Tool usage:
- list_files: discover available files.
- get_file_info: inspect file metadata.
- read_file: read required content.
- search_files: find relevant information.
- write_file: create persistent results.
- patch_file: modify existing files.
- web tools: use only when external information is needed.
For complex tasks:
inspect → retrieve → analyze → save results → continue.
Keep responses concise and focus on completing tasks.'''

    history = read_history(history_path) or [
        {
            'role': 'system',
            'content': system_prompt,
        },
    ]
    '''Nạp lịch sử chat'''

    number_turn = 10
    '''Số turn tối đa được phép lấy vào ngữ cảnh'''

    while True:
        content = input("- USER: ")
        '''Lấy câu hỏi mới của người dùng'''

        if content.lower() in [""]:
            break
        '''Các lệnh thoát'''

        history.append({
            'role': 'user',
            'content': content
        })
        '''Thêm turn mới vào lịch sử'''

        request = {
            # "messages": [history[0]] + history[-number_turn:]
            'messages': history
        }
        '''Tạo dict đầu vào cho src controller'''

        response = controller.invoke(
            request
        )
        '''Gọi chat src'''

        history.append({
            'role': response.role,
            'content': response.content
        })
        '''Thêm phản hồi của turn mới vào lịch sử chat'''

        print("- AGENT:", response.content)

        write_history(
            data=history,
            history_path=history_path
        )
        '''Lưu lịch sử chat'''


if __name__ == "__main__":
    main()
