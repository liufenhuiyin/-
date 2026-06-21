from docx import Document
import re

# ===== 1. 读取文件 =====
file_path = "作业治疗学习题集 (1).docx"
doc = Document(file_path)

text = "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])

# ===== 2. 分离答案区 =====
if "参考答案" in text:
    main_text, answer_text = text.split("参考答案", 1)
else:
    main_text, answer_text = text, ""

# ===== 3. 构建答案映射 =====
answer_map = dict(re.findall(r'(\d+)\s*[\.．]?\s*([A-E])', answer_text))

# ===== 4. 按题号切题 =====
questions = re.split(r'\n(?=\d+\s*[\.．])', main_text)

md = []

# ===== 5. 组装Markdown =====
for q in questions:
    q = q.strip()
    if not q:
        continue

    m = re.match(r'(\d+)\s*[\.．]\s*(.*)', q, re.S)
    if not m:
        continue

    num, content = m.groups()
    ans = answer_map.get(num, "N/A")

    md.append(f"## Q{num}\n")
    md.append(content.strip())
    md.append(f"\n\n答案：{ans}\n")
    md.append("\n---\n")

# ===== 6. 输出文件 =====
output_file = "OT_作业治疗_题库.md"

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print("转换完成：", output_file)