# blk_analyzer.py
import sys
import argparse

def classify_io(io_size, last_lba, current_lba):
    """判断当前IO是否为顺序IO"""
    if last_lba is None:
        return "random"
    if last_lba + io_size == current_lba:
        return "sequential"
    return "random"

def get_op_type(op_str):
    """判断操作类型：Read, Write, Discard"""
    if 'R' in op_str:
        return 'Read'
    elif 'W' in op_str:
        return 'Write'
    elif 'D' in op_str:
        return 'Discard'
    else:
        return 'Other'

def get_process_name(cmd_name):
    """获取进程名称，合并类似 kworker/127、workflow_75 这样的进程"""
    if '/' in cmd_name:
        return cmd_name.split('/')[0]
    elif ':' in cmd_name:
        return cmd_name.split(':')[0]
    elif '_' in cmd_name:
        parts = cmd_name.split('_')
        # 检查最后一个部分是否是数字
        if parts[-1].isdigit():
            return '_'.join(parts[:-1])
        return cmd_name
    return cmd_name

def print_by_size(size, io_stats, grand_total_io, by_process=False):
    total_io = 0
    read_count = 0
    write_count = 0
    discard_count = 0
    other_count = 0
    
    # 先计算总数
    if by_process:
        for op_type in io_stats[size]:
            for proc_name in io_stats[size][op_type]:
                op_total = io_stats[size][op_type][proc_name]["sequential"] + io_stats[size][op_type][proc_name]["random"]
                total_io += op_total
                if op_type == 'Read':
                    read_count += op_total
                elif op_type == 'Write':
                    write_count += op_total
                elif op_type == 'Discard':
                    discard_count += op_total
                elif op_type == 'Other':
                    other_count += op_total
    else:
        for op_type in io_stats[size]:
            op_total = io_stats[size][op_type]["sequential"] + io_stats[size][op_type]["random"]
            total_io += op_total
            if op_type == 'Read':
                read_count += op_total
            elif op_type == 'Write':
                write_count += op_total
            elif op_type == 'Discard':
                discard_count += op_total
            elif op_type == 'Other':
                other_count += op_total
    
    if total_io == 0:
        return
    
    size_percentage = (total_io / grand_total_io) * 100
    
    # 构建比例信息字符串
    rw_info = []
    if read_count > 0:
        read_pct = (read_count / total_io) * 100
        rw_info.append(f"R:{read_pct:.2f}%")
    if write_count > 0:
        write_pct = (write_count / total_io) * 100
        rw_info.append(f"W:{write_pct:.2f}%")
    if discard_count > 0:
        discard_pct = (discard_count / total_io) * 100
        rw_info.append(f"D:{discard_pct:.2f}%")
    if other_count > 0:
        other_pct = (other_count / total_io) * 100
        rw_info.append(f"O:{other_pct:.2f}%")
    rw_str = '/'.join(rw_info)
    
    print(f"IO Size: {size} bytes (count: {total_io}, {size_percentage:.2f}% of all IO, {rw_str})")
    
    # 根据是否按进程分输出不同的内容
    if by_process:
        for op_type in sorted(io_stats[size].keys()):
            # 先计算该操作类型的总数
            op_type_total = 0
            for proc_name in io_stats[size][op_type]:
                op_total = io_stats[size][op_type][proc_name]["sequential"] + io_stats[size][op_type][proc_name]["random"]
                op_type_total += op_total
            
            print(f"  {op_type}:")
            for proc_name in sorted(io_stats[size][op_type].keys()):
                proc_stats = io_stats[size][op_type][proc_name]
                op_total = proc_stats["sequential"] + proc_stats["random"]
                if op_total == 0:
                    continue
                proc_percentage = (op_total / op_type_total) * 100
                seq_percentage = (proc_stats["sequential"] / op_total) * 100
                rand_percentage = (proc_stats["random"] / op_total) * 100
                print(f"    {proc_name} ({proc_percentage:.1f}%):")
                print(f"        Sequential: {proc_stats['sequential']} ({seq_percentage:.2f}%)")
                print(f"        Random: {proc_stats['random']} ({rand_percentage:.2f}%)")
    else:
        for op_type in sorted(io_stats[size].keys()):
            op_stats = io_stats[size][op_type]
            op_total = op_stats["sequential"] + op_stats["random"]
            if op_total == 0:
                continue
            seq_percentage = (op_stats["sequential"] / op_total) * 100
            rand_percentage = (op_stats["random"] / op_total) * 100
            print(f"  {op_type}:")
            print(f"    Sequential: {op_stats['sequential']} ({seq_percentage:.2f}%)")
            print(f"    Random: {op_stats['random']} ({rand_percentage:.2f}%)")
    print()

def analyze_blktrace(input_lines, filter_arg=None, by_process=False):
    io_stats = {}
    last_lba = None
    overall_stats = {"sequential": 0, "random": 0}

    for line in input_lines:
        parts = line.strip().split(", ")
        if len(parts) != 8:
            continue

        # 解析字段
        timestamp = float(parts[0])
        pid = int(parts[1])
        command_name = parts[2]
        io_type = parts[3]
        op_type = parts[4]
        lba = int(parts[5])
        block_count = int(parts[6])
        io_size = int(parts[7])

        # 忽略 IO size 为 0 的情况
        if io_size == 0:
            continue

        # 判断操作类型
        op_category = get_op_type(op_type)
        
        # 获取进程名称（合并相同名称的进程）
        proc_name = get_process_name(command_name)

        # 分类IO大小
        if io_size not in io_stats:
            io_stats[io_size] = {}
        if op_category not in io_stats[io_size]:
            if by_process:
                io_stats[io_size][op_category] = {}
            else:
                io_stats[io_size][op_category] = {"sequential": 0, "random": 0}
        
        # 判断是顺序IO还是随机IO
        io_class = classify_io(block_count, last_lba, lba)
        
        if by_process:
            if proc_name not in io_stats[io_size][op_category]:
                io_stats[io_size][op_category][proc_name] = {"sequential": 0, "random": 0}
            io_stats[io_size][op_category][proc_name][io_class] += 1
        else:
            io_stats[io_size][op_category][io_class] += 1
        
        overall_stats[io_class] += 1

        # 更新最后的LBA
        last_lba = lba

    # 计算总 IO 数
    grand_total_io = overall_stats['sequential'] + overall_stats['random']

    # 处理筛选
    filtered_sizes = []
    for size in sorted(io_stats.keys()):
        # 计算该 size 的总 IO 数
        total_for_size = 0
        if by_process:
            for op_type in io_stats[size]:
                for proc_name in io_stats[size][op_type]:
                    total_for_size += io_stats[size][op_type][proc_name]["sequential"] + io_stats[size][op_type][proc_name]["random"]
        else:
            for op_type in io_stats[size]:
                total_for_size += io_stats[size][op_type]["sequential"] + io_stats[size][op_type]["random"]
        
        if filter_arg is None:
            filtered_sizes.append(size)
        elif isinstance(filter_arg, (int, float)):
            # 特定 IO size
            if size == filter_arg:
                filtered_sizes.append(size)
        elif isinstance(filter_arg, str):
            if "percentage" in filter_arg.lower():
                # 百分比大于某个值：percentage>10 或 >percentage10
                if ">" in filter_arg:
                    try:
                        percentage_str = filter_arg.split(">")[1].replace("%", "").strip()
                        percentage = float(percentage_str)
                        size_percent = (total_for_size / grand_total_io) * 100
                        if size_percent > percentage:
                            filtered_sizes.append(size)
                    except (IndexError, ValueError):
                        pass
            elif filter_arg.startswith(">"):
                # 大于某个具体值：>4096
                try:
                    threshold = int(filter_arg[1:])
                    if size > threshold:
                        filtered_sizes.append(size)
                except ValueError:
                    pass

    # 输出结果
    for size in filtered_sizes:
        print_by_size(size, io_stats, grand_total_io, by_process)

    print(f"Overall Sequential IO: {overall_stats['sequential']} ({overall_stats['sequential']/grand_total_io*100:.2f}%)")
    print(f"Overall Random IO: {overall_stats['random']} ({overall_stats['random']/grand_total_io*100:.2f}%)")
    print(f"Total IO count: {grand_total_io}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze block IO traces.')
    parser.add_argument('--filter', help='Filter IO sizes: specific size (e.g., 4096), greater than (e.g., >4096), or percentage greater (e.g., percentage>10)')
    parser.add_argument('-c', '--by-process', action='store_true', help='Group and summarize by process name')
    args = parser.parse_args()

    filter_arg = args.filter

    # 处理 filter 参数
    if filter_arg is not None and filter_arg.isdigit():
        filter_arg = int(filter_arg)

    input_lines = sys.stdin.readlines()
    analyze_blktrace(input_lines, filter_arg, args.by_process)