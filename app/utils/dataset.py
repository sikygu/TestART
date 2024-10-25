import pickle
import zipfile
import os
from io import BytesIO
import tiktoken
from typing import List
import javalang
from javalang.tree import ClassDeclaration, MethodDeclaration
from typing import List
import random as r

from app.classes import Markdown
from app.constants import Config, CONFIG


def get_type_string(type):
    if type is None:
        return 'void'
    # 处理基本类型和引用类型
    type_str = ''
    if isinstance(type, javalang.tree.ReferenceType):
        type_str = type.name
        if type.arguments:
            args = ', '.join(get_type_string(arg.type) for arg in type.arguments if arg.type is not None)
            type_str += f"<{args}>"
    elif isinstance(type, javalang.tree.BasicType):
        type_str = type.name
    else:
        type_str = str(type)

    # 处理数组类型
    dimensions = ''.join('[]' for _ in range(len(type.dimensions))) if hasattr(type, 'dimensions') else ''
    return f"{type_str}{dimensions}"


def get_method_signatures(java_code):
    tree = javalang.parse.parse(java_code)
    method_signatures = []

    for _, class_declaration in tree.filter(javalang.tree.ClassDeclaration):
        for method in class_declaration.methods:
            # 获取方法的返回类型，包括泛型信息和数组
            return_type = get_type_string(method.return_type)

            # 获取方法的参数类型，包括泛型信息和数组
            params = []
            for parameter in method.parameters:
                param_type = get_type_string(parameter.type)
                if parameter.varargs:
                    param_type += "..."
                params.append(param_type)

            # 构建方法签名
            method_signature = f"{method.name}({', '.join(params)}) : {return_type}"
            method_signatures.append(method_signature)

    return method_signatures


def compress_data(content: str, signature: str, method_infos: List[dict]) -> str:
    # 将内容按行分割
    lines = content.split('\n')

    # 为了不影响行号，我们需要从后往前替换
    # 首先对method_infos按照start从大到小排序
    method_infos_sorted = sorted(method_infos, key=lambda x: -x['start'])

    # 遍历每个方法信息
    for method_info in method_infos_sorted:
        # 如果签名不匹配，则压缩方法体
        if method_info['signature'] != signature:
            # 注意，行号从1开始，列表索引从0开始，所以要减1
            start_index = method_info['start'] - 1
            end_index = method_info['end']
            # 将方法体替换为方法签名
            lines[start_index:end_index] = [method_info['signature']]

    # 将修改后的行列表重新组合成一个字符串
    compressed_content = '\n'.join(lines)
    return compressed_content


def remove_comments(input_string):
    import re
    pattern = r'/\*\*?\s.*?\*/'
    return re.sub(pattern, '', input_string, flags=re.DOTALL)

total_num = 0
def get_class_info(file: str):
    global total_num
    file = remove_comments(file)
    # handle \u000a
    file = file.replace("\\u000a", "")

    # magic replace
    magic_table = {
        "\'{\'": "6416864816840",
        "\'}\'": "6416864816841",
    }
    for k, v in magic_table.items():
        file = file.replace(k, v)

    file_lines = file.splitlines()
    try:
        tree = javalang.parse.parse(file)
        # assert len(tree.types) == 1  # 一个文件只有一个类
    except Exception as e:
        raise e
    clazz: ClassDeclaration = tree.types[0]
    print("processing", clazz.name, clazz.modifiers)
    if not isinstance(clazz, ClassDeclaration) or 'abstract' in clazz.modifiers:
        return None, None, None
    clazz_name = clazz.name
    methods: List[MethodDeclaration] = clazz.methods

    method_infos = []
    all_method_infos = []
    # total_num = total_num + len(methods)
    # print(f"methods: {total_num}(+{len(methods)})")
    for method in methods:
        valid_focal_method = 'public' in method.modifiers

        start = method.position[0]

        def get_method_end(method):
            def f(node):
                if hasattr(node, 'children'):
                    for child in node.children:
                        yield from f(child)

                if isinstance(node, list):
                    for child in node:
                        yield from f(child)

                if hasattr(node, 'position'):
                    if node.position is not None:
                        yield node.position[0]

            stmt_set = set(f(method))
            return max(stmt_set) + 1


        end = get_method_end(method)
        content = file_lines[start - 1:end]
        # 缩进处理
        indent = len(content[0]) - len(content[0].lstrip())
        content = [line[indent:] for line in content]
        content = "\n".join(content)

        # 获取方法的返回类型，包括泛型信息和数组
        return_type = get_type_string(method.return_type)

        # 获取方法的参数类型，包括泛型信息和数组
        params = []
        for parameter in method.parameters:
            param_type = get_type_string(parameter.type)
            if parameter.varargs:
                param_type += "..."
            params.append(param_type)

        # 构建方法签名
        method_signature = f"{method.name}({', '.join(params)}) : {return_type}"
        info = {
            "signature": method_signature,
            "name": method.name,
            "start": start,
            "end": end,
            "content": content,
        }
        if valid_focal_method:
            print(f"valid method: {method_signature} ({start}-{end})")
            method_infos.append(info)
        else:
            print(f"invalid method: {method.modifiers} {method_signature} ({start}-{end})")
        all_method_infos.append(info)

    for mi in method_infos:
        mi["compressed_content"] = compress_data(file, mi["signature"], all_method_infos)

    # 还原magic_string
    for k, v in magic_table.items():
        file = file.replace(v, k)

    return clazz_name, file, method_infos


def process_zip_dataset(fp: str, filename: str):
    tiktoken_encoder = tiktoken.encoding_for_model('gpt-3.5-turbo')
    # 准备一个列表来存储结果
    result_list = []

    # 临时内存文件
    new_zip_data = BytesIO()

    # 打开原始 ZIP 文件
    with zipfile.ZipFile(fp, 'r') as zip_ref:
        # 创建一个新的 ZipFile 对象，用于存储修改后的内容
        with zipfile.ZipFile(new_zip_data, 'w', zipfile.ZIP_DEFLATED) as new_zip_ref:
            # 遍历原始 ZIP 文件中的所有文件
            for file_info in zip_ref.infolist():
                if 'package-info.java' in file_info.filename:
                    continue
                filepath = file_info.filename
                file_data = zip_ref.read(filepath)
                # 检查是否是需要修改的文件
                if filepath.endswith(".java") and "src/main/java" in filepath:
                    # 对文件内容进行解码
                    decoded_data = file_data.decode(errors="replace")
                    # 处理文件内容
                    print("trying process", filepath)
                    clazz_name, new_file_data, method_infos = get_class_info(decoded_data)
                    # 如果处理后的文件不为空，则使用修改后的文件数据
                    if clazz_name is not None:
                        file_data = new_file_data
                        _ = filepath.split("src/main/java/")[1][:-5]
                        package_reference = "" if "/" not in _ else _.replace("/", ".").replace(
                            f".{clazz_name}", "")
                        # 假设 tiktoken_encoder 是您定义的一个对象，用于编码文件数据
                        tokens = len(tiktoken_encoder.encode(file_data))
                        if tokens > 15000:
                            print("tokens > 15000", clazz_name, tokens)
                        result_list.append({
                            "class_name": clazz_name,
                            "content": file_data,
                            "methods": sorted(method_infos, key=lambda x: x["start"]),
                            "tokens": tokens,
                            "package_reference": package_reference,
                            "lines": len(file_data.splitlines())
                        })
                # 将原始或修改后的文件数据写入新的 ZIP 文件中
                new_zip_ref.writestr(file_info, file_data)

    print(f"clazz num: {len(result_list)}")
    print(f"method num: {sum([len(clazz['methods']) for clazz in result_list])}")

    # 验证数据集正确性
    def has_overlap(intervals):
        intervals.sort(key=lambda x: x[0])  # 按照起点进行排序
        for i in range(1, len(intervals)):
            if intervals[i][0] < intervals[i - 1][1]:  # 如果下一个区间的起点小于上一个区间的终点，说明有重合
                print("overlap:" ,intervals[i], intervals[i - 1])
                return True
        return False

    li = []

    for class_info in result_list:
        for method_info in class_info["methods"]:
            li.append((class_info["package_reference"],class_info["class_name"], method_info["signature"], method_info["start"], method_info["end"]))
        if has_overlap([(method_info["start"], method_info["end"]) for method_info in class_info["methods"]]):
            print(f"overlap found! {class_info['class_name']}")
            assert False
    li_map = [
        {
            "package": item[0],
            "class_name": item[1],
            "method_name": item[2],
            "start": item[3],
            "end": item[4],
        }
        for item in li
    ]
    with open(f"{CONFIG.dataset_folder}/{filename}_info.md", "w") as f:
        markdown = Markdown().table(li_map).build()
        f.write(markdown)
    with open(f"{CONFIG.dataset_folder}/{filename}_info.json", "w") as f:
        import json
        json.dump(li_map, f)

    # 保存压缩后的对象到文件
    with open(f"{CONFIG.dataset_folder}/{filename}.pkl", "wb") as f:
        pickle.dump({"data": sorted(result_list, key=lambda x: x["class_name"])}, f)

    # 关闭内存中的 ZIP 文件
    new_zip_data.seek(0)
    # 将新的 ZIP 文件数据写入到原始文件路径
    with open(f"{CONFIG.dataset_folder}/{filename}.zip", 'wb') as f:
        f.write(new_zip_data.read())
    # 关闭内存文件
    new_zip_data.close()

def code_to_zip(code: str, filename: str):
    # 创建一个zip文件
    with zipfile.ZipFile(f"{CONFIG.dataset_folder}/{filename}.zip", 'w', zipfile.ZIP_DEFLATED) as new_zip_ref:
        new_zip_ref.writestr(f"src/main/java/{filename}.java", code)

__all__ = ['process_zip_dataset']
