#!/usr/bin/env python3
"""
更新课程HTML模板中的练习和作业内容
从markdown文件中提取完整的描述、提示等信息
"""
import re
import os
from pathlib import Path


def parse_exercise_title(line):
    """从标题行提取练习标题和难度"""
    # 匹配 ### 练习1（基础） 或 ### 练习1 基础 或 **练习1（基础）**
    match = re.search(r'练习\s*(\d+)(?:[（(]([^）)]+)[）)])?', line)
    if match:
        num = match.group(1)
        difficulty = match.group(2) if match.group(2) else '基础'
        # 简化难度名称
        if any(x in difficulty for x in ['进阶', '中等', '练习']):
            difficulty = '进阶'
        elif '挑战' in difficulty:
            difficulty = '挑战'
        return num, difficulty
    return None, None


def parse_homework_title(line):
    """从标题行提取作业标题和是否必做"""
    # 清理 markdown 粗体标记 - 移除所有 **
    line = line.replace('**', '')

    # 格式1：### 作业1：标题 或 ### 作业1：xxx（必做）
    match = re.search(r'作业\s*(\d+)[：:]\s*(.+)', line)
    if match:
        num = match.group(1)
        title = match.group(2).strip()
        required = '必做' in title
        return num, required, title

    # 格式2：### 作业1（必做）标题 或 ### 作业1（选做）标题
    match = re.search(r'作业\s*(\d+)[（(]([^）)]+)[）)]\s*(.+)', line)
    if match:
        num = match.group(1)
        difficulty = match.group(2)
        title = match.group(3).strip()
        required = '必做' in difficulty
        return num, required, title

    # 格式3：### 作业1 标题（空格分隔，没有冒号）
    match = re.search(r'作业\s*(\d+)\s+([^（]+)', line)
    if match:
        num = match.group(1)
        title = match.group(2).strip()
        required = '必做' in title or '作业1' in line
        return num, required, title

    return None, None, None


def extract_code_block(lines, start_idx):
    """从指定位置开始提取代码块"""
    if start_idx >= len(lines) or '```python' not in lines[start_idx]:
        return '', start_idx

    code_lines = []
    start_idx += 1  # 跳过 ```python 行
    while start_idx < len(lines) and '```' not in lines[start_idx]:
        code_lines.append(lines[start_idx])
        start_idx += 1
    return '\n'.join(code_lines).strip(), start_idx + 1


def extract_hint(text):
    """从文本中提取提示"""
    hints = []
    # 匹配 **提示：** 或 **提示：**
    hint_pattern = re.compile(r'\*\*提示[：:]\*\*\s*(.+?)(?=\n\n|\*\*|$)', re.DOTALL)
    for match in hint_pattern.finditer(text):
        hint = match.group(1).strip()
        # 清理提示文本
        hint = re.sub(r'\*\*(.+?)\*\*', r'\1', hint)
        hints.append(hint)
    return hints


def parse_exercise_block(lines, start_idx):
    """解析一个练习块"""
    if start_idx >= len(lines):
        return None, start_idx

    line = lines[start_idx].strip()

    # 检查是否是练习标题（### 或 ** 都可以）
    if '练习' not in line:
        return None, start_idx
    if not line.startswith('###') and not line.startswith('**'):
        return None, start_idx

    num, difficulty = parse_exercise_title(line)
    if not num:
        return None, start_idx

    start_idx += 1
    description_parts = []
    code_template = ''
    hints = []

    # 收集描述直到遇到代码块、提示或下一个标题
    while start_idx < len(lines):
        current_line = lines[start_idx].strip()

        # 遇到新标题结束（### 或 ** 开头）
        if (current_line.startswith('###') or current_line.startswith('##') or
            (current_line.startswith('**') and '练习' in current_line) or
            (current_line.startswith('**') and '作业' in current_line)):
            break

        # 遇到代码块
        if current_line == '```python':
            code_template, start_idx = extract_code_block(lines, start_idx)
            continue

        # 遇到提示
        if '**提示**' in current_line or '**提示：**' in current_line:
            hints = extract_hint('\n'.join(lines[start_idx:start_idx+5]))
            break

        # 收集描述
        if current_line and not current_line.startswith('---'):
            description_parts.append(current_line)

        start_idx += 1

    description = ' '.join(description_parts).strip()

    # 清理描述中的markdown格式
    description = re.sub(r'\*\*(.+?)\*\*', r'\1', description)

    return {
        'id': f'ex{num}',
        'title': f'练习{num}({difficulty})' if difficulty != '基础' else f'练习{num}',
        'difficulty': difficulty,
        'description': description,
        'codeTemplate': code_template,
        'hints': hints
    }, start_idx


def parse_homework_block(lines, start_idx):
    """解析一个作业块"""
    if start_idx >= len(lines):
        return None, start_idx

    line = lines[start_idx].strip()

    # 检查是否是作业标题（### 或 ** 都可以）
    if '作业' not in line:
        return None, start_idx
    if not line.startswith('###') and not line.startswith('**'):
        return None, start_idx

    num, required, extra_title = parse_homework_title(line)
    if not num:
        return None, start_idx

    start_idx += 1
    description_parts = []
    requirements = []
    code_template = ''
    hints = []
    features = []

    # 收集内容直到遇到新标题
    while start_idx < len(lines):
        current_line = lines[start_idx].strip()

        # 遇到新标题结束（### 或 ** 开头）
        if (current_line.startswith('###') or current_line.startswith('##') or
            (current_line.startswith('**') and '练习' in current_line) or
            (current_line.startswith('**') and '作业' in current_line)):
            break

        # 遇到代码块
        if current_line == '```python':
            code_template, start_idx = extract_code_block(lines, start_idx)
            continue

        # 遇到bullet list项
        if current_line.startswith('- '):
            req = current_line[2:].strip()
            # 清理格式
            req = re.sub(r'`([^`]+)`', r'\1', req)
            requirements.append(req)

        # 遇到示例输出
        if '示例输出' in current_line:
            start_idx += 1
            continue

        # 遇到提示
        if '**提示**' in current_line or '**提示：**' in current_line:
            hints = extract_hint('\n'.join(lines[start_idx:start_idx+5]))
            start_idx += 1
            continue

        # 收集描述
        if current_line and not current_line.startswith('---'):
            # 过滤掉示例输出的标记
            if '```' not in current_line:
                description_parts.append(current_line)

        start_idx += 1

    description = ' '.join(description_parts).strip()
    # 清理描述中的markdown格式
    description = re.sub(r'\*\*(.+?)\*\*', r'\1', description)
    description = re.sub(r'`([^`]+)`', r'\1', description)

    title = extra_title if extra_title else f'作业{num}'

    return {
        'id': f'hw{num}',
        'title': title,
        'required': required,
        'description': description,
        'requirements': requirements,
        'codeTemplate': code_template,
        'hints': hints
    }, start_idx


def parse_markdown_file(filepath):
    """解析markdown文件，提取所有练习和作业"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    exercises = []
    homework = []

    in_exercise_section = False
    in_homework_section = False

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 找到课堂练习部分（必须是 ## 开头）
        if line.startswith('## ') and ('四、课堂练习' in line or '课堂练习' in line):
            in_exercise_section = True
            in_homework_section = False
            i += 1
            continue

        # 找到课后作业部分（必须是 ## 开头，且是二级标题）
        if line.startswith('## ') and ('课后作业' in line or ('作业' in line and '五' in line)) and '练习' not in line:
            in_exercise_section = False
            in_homework_section = True
            i += 1
            continue

        # 找到项目任务部分，停止解析
        if '## 六、项目' in line:
            break

        # 解析练习
        if in_exercise_section:
            ex, new_i = parse_exercise_block(lines, i)
            if ex:
                exercises.append(ex)
                i = new_i
                continue

        # 解析作业
        if in_homework_section:
            hw, new_i = parse_homework_block(lines, i)
            if hw:
                homework.append(hw)
                i = new_i
                continue

        i += 1

    return exercises, homework


def escape_js_string(s):
    """转义字符串用于JavaScript"""
    if s is None:
        return ''
    s = str(s)
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '')
    return s


def generate_course_data_js(exercises, homework):
    """生成courseData的JavaScript代码"""
    ex_items = []
    for ex in exercises:
        ex_items.append(f'''          {{
            id: "{ex['id']}",
            title: "{escape_js_string(ex.get('title', ''))}",
            difficulty: "{ex.get('difficulty', '基础')}",
            description: "{escape_js_string(ex.get('description', ''))}",
            codeTemplate: "",
            hints: {ex.get('hints', [])}
          }}''')

    hw_items = []
    for hw in homework:
        hw_items.append(f'''          {{
            id: "{hw['id']}",
            title: "{escape_js_string(hw.get('title', ''))}",
            required: {str(hw.get('required', True)).lower()},
            description: "{escape_js_string(hw.get('description', ''))}",
            requirements: {hw.get('requirements', [])},
            codeTemplate: "",
            testInputs: [],
            hints: {hw.get('hints', [])}
          }}''')

    exercises_section = ',\n'.join(ex_items)
    homework_section = ',\n'.join(hw_items)
    return '''const courseData = {
      exercises: [
%s
      ],
      homework: [
%s
      ]
    };''' % (exercises_section, homework_section)


def update_html_file(html_path, exercises, homework):
    """更新HTML文件中的courseData"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 生成新的courseData
    new_course_data = generate_course_data_js(exercises, homework)

    # 替换旧的courseData
    # 找到 courseData = { 开始的位置
    start_pattern = r'const courseData = \{'
    end_pattern = r'\};[\s\n]*exercises'

    start_match = re.search(start_pattern, content)
    if not start_match:
        print(f"  警告: 在 {html_path} 中找不到 courseData")
        return False

    # 找到courseData结束的位置（需要匹配嵌套的对象）
    search_start = start_match.start()
    brace_count = 0
    in_string = False
    string_char = None
    end_pos = search_start

    for i, c in enumerate(content[search_start:]):
        if in_string:
            if c == string_char and content[search_start + i - 1] != '\\':
                in_string = False
        else:
            if c in '"' or c == "'":
                in_string = True
                string_char = c
            elif c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = search_start + i + 1
                    break

    # 提取courseData之前和之后的内容
    before = content[:start_match.start()]
    after = content[end_pos:]

    # 在 after 中找到 exercises: [ 或 homework: [ 的位置
    exercises_match = re.search(r'exercises:\s*\[', after)
    homework_match = re.search(r'homework:\s*\[', after)

    if exercises_match and homework_match:
        # 找到 exercises 结束的位置
        ex_end = after.find(']', exercises_match.end())
        hw_start = after.find('homework:', exercises_match.end())
        hw_end = after.find(']', hw_start + len('homework: ['))

        # 替换 exercises 和 homework 部分
        new_exercises = 'exercises: [\n        ]'
        new_homework = 'homework: [\n        ]'

        after = after[:exercises_match.start()] + new_exercises + after[ex_end+1:]
        after = after[:hw_start] + new_homework + after[hw_end+1:]

    # 组合新内容
    new_content = before + new_course_data + after

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return True


def main():
    course_dir = Path('/workspace/course')
    template_dir = Path('/workspace/hyperframes/registry/examples/course-template')

    print('开始更新课程模板...\n')

    for md_file in sorted(course_dir.glob('*.md')):
        week_match = re.search(r'第(\d+)周', md_file.name)
        if not week_match:
            continue

        week_num = int(week_match.group(1))
        html_path = template_dir / f'week{week_num:02d}.html'

        if not html_path.exists():
            print(f'跳过: {md_file.name} (对应的HTML不存在)')
            continue

        print(f'处理: {md_file.name}')

        # 解析markdown
        exercises, homework = parse_markdown_file(md_file)

        if not exercises and not homework:
            print(f'  警告: 没有找到练习或作业')
            continue

        print(f'  找到 {len(exercises)} 个练习, {len(homework)} 个作业')

        # 更新HTML
        if update_html_file(html_path, exercises, homework):
            print(f'  更新完成: {html_path.name}')

    print('\n完成!')


if __name__ == '__main__':
    main()
