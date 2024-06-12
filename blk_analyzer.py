# blk_analyzer.py
import sys

def classify_io(io_size, last_lba, current_lba):
    """判断当前IO是否为顺序IO"""
    if last_lba is None:
        return "random"
    if last_lba + io_size == current_lba:
        return "sequential"
    return "random"

def print_by_size(size, io_stats):
    total_io = io_stats[size]["sequential"] + io_stats[size]["random"]
    if total_io == 0:
        return
    seq_percentage = (io_stats[size]["sequential"] / total_io) * 100
    rand_percentage = (io_stats[size]["random"] / total_io) * 100
    print(f"IO Size: {size} bytes")
    print(f"  Sequential IO: {io_stats[size]['sequential']} ({seq_percentage:.2f}%)")
    print(f"  Random IO: {io_stats[size]['random']} ({rand_percentage:.2f}%)\n")

def analyze_blktrace(input_lines):
    io_stats = {}
    last_lba = None
    overall_stats = {"sequential": 0, "random": 0}

    for line in input_lines:
        parts = line.strip().split(", ")
        if len(parts) != 7:
            continue

        # 解析字段
        timestamp = float(parts[0])
        pid = int(parts[1])
        command_name = parts[2]
        io_type = parts[3]
        lba = int(parts[4])
        block_count = int(parts[5])
        io_size = int(parts[6])

        # 分类IO大小
        if io_size not in io_stats:
            io_stats[io_size] = {"sequential": 0, "random": 0}

        # 判断是顺序IO还是随机IO
        io_class = classify_io(block_count, last_lba, lba)
        io_stats[io_size][io_class] += 1
        overall_stats[io_class] += 1

        # 更新最后的LBA
        last_lba = lba

    # 输出结果
    for size in sorted(io_stats.keys()):
        print_by_size(size, io_stats)

    total_io = overall_stats['sequential'] + overall_stats['random']
    print(f"Overall Sequential IO: {overall_stats['sequential']} ({overall_stats['sequential']/total_io*100:.2f}%)")
    print(f"Overall Random IO: {overall_stats['random']} ({overall_stats['random']/total_io*100:.2f}%)\n")

if __name__ == "__main__":
    input_lines = sys.stdin.readlines()
    analyze_blktrace(input_lines)