#!/usr/bin/env python3

# blk_analyzer.py
import sys
import argparse

def classify_io(last_end_lba, current_lba):
    """判断当前IO是否为顺序IO"""
    if last_end_lba is None:
        return "random"
    if last_end_lba == current_lba:
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
    """获取进程名称，合并类似 kworker/52:1、workflow_75 这样的进程"""
    if '/' in cmd_name:
        base, suffix = cmd_name.split('/', 1)
        if base == 'kworker':
            return 'kworker'
        suffix_no_colon = suffix.replace(':', '')
        if suffix_no_colon.isdigit():
            return base
        elif ':' in suffix:
            suffix_parts = suffix.split(':', 1)
            if suffix_parts[0].isdigit():
                return f"{base}:{suffix_parts[1]}"
        return cmd_name
    elif ':' in cmd_name:
        base, suffix = cmd_name.split(':', 1)
        if suffix.isdigit():
            return base
        return cmd_name
    elif '_' in cmd_name:
        parts = cmd_name.split('_')
        if parts[-1].isdigit():
            return '_'.join(parts[:-1])
        return cmd_name
    return cmd_name

def format_duration_us(value):
    if value >= 1000000:
        return f"{value / 1000000:.2f}s"
    if value >= 1000:
        return f"{value / 1000:.2f}ms"
    return f"{value:.2f}us"

def format_size_kb(value):
    if value >= 1024:
        return f"{value / 1024:.2f}MB"
    return f"{value:.2f}KB"

def format_rate_kb(value):
    if value >= 1024:
        return f"{value / 1024:.2f}MB/s"
    return f"{value:.2f}KB/s"

def get_latency_summary(latencies):
    if not latencies:
        return None
    return min(latencies), max(latencies), sum(latencies) / len(latencies)

def format_latency_detail(latencies):
    summary = get_latency_summary(latencies)
    if summary is None:
        return "latency unavailable: no matching D event"
    min_latency, max_latency, avg_latency = summary
    return f"min: {format_duration_us(min_latency)}, max: {format_duration_us(max_latency)}, mean: {format_duration_us(avg_latency)}"

def format_latency(latencies):
    return f" ({format_latency_detail(latencies)})"

def add_pending_range(pending_ios, op_category, item):
    if op_category not in pending_ios:
        pending_ios[op_category] = []
    pending_ios[op_category].append(item)

def match_pending_range(pending_ios, op_category, lba, block_count):
    pending = pending_ios.get(op_category, [])
    if not pending:
        return []

    c_start = lba
    c_end = lba + block_count
    
    selected = []
    covered_blocks = 0
    
    i = 0
    while i < len(pending):
        item = pending[i]
        d_start = item["lba"]
        d_end = d_start + item["block_count"]
        
        if d_start >= c_start and d_end <= c_end:
            selected.append(item)
            covered_blocks += item["block_count"]
            pending.pop(i)
            if covered_blocks >= block_count * 0.95:
                break
        else:
            i += 1
    
    if covered_blocks < block_count * 0.95:
        return []
    
    return selected

def get_latency_compact(latencies):
    summary = get_latency_summary(latencies)
    if summary is None:
        return "-"
    min_latency, max_latency, avg_latency = summary
    return f"{format_duration_us(min_latency)}/{format_duration_us(avg_latency)}/{format_duration_us(max_latency)}"

def print_by_size(size, io_stats, grand_total_io, by_process=False, show_latency=False):
    total_io = 0
    read_count = 0
    write_count = 0
    discard_count = 0
    other_count = 0
    
    # 先计算总数
    if by_process:
        for op_type in io_stats[size]:
            for proc_name in io_stats[size][op_type]:
                proc_stats = io_stats[size][op_type][proc_name]
                op_total = proc_stats["sequential"] + proc_stats["random"]
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
            
            latencies = []
            for proc_name in io_stats[size][op_type]:
                latencies.extend(io_stats[size][op_type][proc_name].get("latencies", []))
            print(f"  {op_type}:{get_latency_compact(latencies) if show_latency else ''}")
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
        if show_latency:
            print(f"    {'Pattern':<18} {'Count':>10} {'Pct':>8} {'LatN':>8} {'min/mean/max':>22}")
            print(f"    {'-' * 18} {'-' * 10} {'-' * 8} {'-' * 8} {'-' * 22}")
            for op_type in sorted(io_stats[size].keys()):
                op_stats = io_stats[size][op_type]
                for io_class, label in (("sequential", "Sequential"), ("random", "Random")):
                    count = op_stats[io_class]
                    if count == 0:
                        continue
                    percentage = (count / total_io) * 100
                    latencies = op_stats.get(f"{io_class}_latencies", [])
                    latency_text = get_latency_compact(latencies)
                    print(f"    {label + ' ' + op_type:<18} {count:>10} {percentage:>7.2f}% {len(latencies):>8} {latency_text:>22}")
        else:
            print(f"    {'Pattern':<18} {'Count':>10} {'Pct':>8}")
            print(f"    {'-' * 18} {'-' * 10} {'-' * 8}")
            for op_type in sorted(io_stats[size].keys()):
                op_stats = io_stats[size][op_type]
                for io_class, label in (("sequential", "Sequential"), ("random", "Random")):
                    count = op_stats[io_class]
                    if count == 0:
                        continue
                    percentage = (count / total_io) * 100
                    print(f"    {label + ' ' + op_type:<18} {count:>10} {percentage:>7.2f}%")
    print()

def parse_blktrace_line(line):
    parts = line.strip().split(", ")
    if len(parts) != 8:
        return None

    try:
        record = {
            "timestamp": float(parts[0]),
            "pid": int(parts[1]),
            "command_name": parts[2],
            "io_type": parts[3].strip(),
            "op_type": parts[4].strip(),
            "lba": int(parts[5]),
            "block_count": int(parts[6]),
            "io_size": int(parts[7]),
            "latency_us": None,
        }
        return record
    except ValueError:
        return None

def record_matches_time_range(record, start_second=None, end_second=None):
    bucket = int(record["timestamp"])
    if start_second is not None and bucket < start_second:
        return False
    if end_second is not None and bucket > end_second:
        return False
    return True

def filter_lines_by_time_range(input_lines, start_second=None, end_second=None):
    if start_second is None and end_second is None:
        return input_lines

    filtered_lines = []
    for line in input_lines:
        record = parse_blktrace_line(line)
        if record is not None and record_matches_time_range(record, start_second, end_second):
            filtered_lines.append(line)
    return filtered_lines

def stat_record_matches_filter(record, filter_arg):
    if filter_arg is None:
        return True
    if isinstance(filter_arg, (int, float)):
        return record["io_size"] == filter_arg
    if isinstance(filter_arg, str) and filter_arg.startswith(">"):
        try:
            return record["io_size"] > int(filter_arg[1:])
        except ValueError:
            return True
    return True

def build_percentage_filter_sizes(input_lines, percentage):
    size_counts = {}
    total_io = 0
    for line in input_lines:
        record = parse_blktrace_line(line)
        if record is None or record["io_size"] == 0 or record["io_type"] != "C":
            continue
        total_io += 1
        size_counts[record["io_size"]] = size_counts.get(record["io_size"], 0) + 1
    return {size for size, count in size_counts.items() if total_io and count / total_io * 100 > percentage}

def parse_percentage_filter(filter_arg):
    if not isinstance(filter_arg, str) or not filter_arg.startswith("pct>") or not filter_arg.endswith("%"):
        return None
    try:
        return float(filter_arg[4:-1])
    except ValueError:
        return None

def parse_count_filter(filter_arg):
    if not isinstance(filter_arg, str) or not filter_arg.startswith("count>"):
        return None
    try:
        return int(filter_arg[6:])
    except ValueError:
        return None

def build_count_filter_sizes(input_lines, count_threshold):
    size_counts = {}
    for line in input_lines:
        record = parse_blktrace_line(line)
        if record is None or record["io_size"] == 0 or record["io_type"] != "C":
            continue
        size_counts[record["io_size"]] = size_counts.get(record["io_size"], 0) + 1
    return {size for size, count in size_counts.items() if count > count_threshold}

def build_output_filter(input_lines, filter_arg, use_completion_counts=False):
    percentage = parse_percentage_filter(filter_arg)
    if percentage is not None:
        if use_completion_counts:
            valid_sizes = build_percentage_filter_sizes(input_lines, percentage)
            return lambda record: record["io_size"] in valid_sizes
        return lambda record: True

    count_threshold = parse_count_filter(filter_arg)
    if count_threshold is not None:
        if use_completion_counts:
            valid_sizes = build_count_filter_sizes(input_lines, count_threshold)
            return lambda record: record["io_size"] in valid_sizes
        return lambda record: True

    return lambda record: stat_record_matches_filter(record, filter_arg)

def print_stat_report(input_lines, filter_arg=None):
    all_records = []
    for line in input_lines:
        record = parse_blktrace_line(line)
        if record is None or record["io_size"] == 0 or record["io_type"] not in ("D", "C"):
            continue
        all_records.append(record)

    if not all_records:
        return

    complete_count = sum(1 for record in all_records if record["io_type"] == "C")
    count_records = [record for record in all_records if record["io_type"] == "C"]

    percentage = parse_percentage_filter(filter_arg)
    count_threshold = parse_count_filter(filter_arg)
    if percentage is not None or count_threshold is not None:
        size_counts = {}
        for record in count_records:
            size_counts[record["io_size"]] = size_counts.get(record["io_size"], 0) + 1
        total_io = len(count_records)
        if percentage is not None:
            valid_sizes = {size for size, count in size_counts.items() if total_io and count / total_io * 100 > percentage}
        else:
            valid_sizes = {size for size, count in size_counts.items() if count > count_threshold}
    else:
        valid_sizes = None

    def selected_count_record(record):
        if record["io_type"] != "C":
            return False
        if valid_sizes is not None:
            return record["io_size"] in valid_sizes
        return stat_record_matches_filter(record, filter_arg)

    stats = {}
    service_times = []
    pending_dispatch = {}

    def get_bucket(ts):
        return int(ts)

    def ensure_bucket(bucket):
        if bucket not in stats:
            stats[bucket] = {
                "read_ios": 0,
                "write_ios": 0,
                "read_kb": 0.0,
                "write_kb": 0.0,
                "read_req_size": 0,
                "write_req_size": 0,
            }

    def add_stat(record):
        bucket = get_bucket(record["timestamp"])
        ensure_bucket(bucket)
        op_category = get_op_type(record["op_type"])
        io_size = record["io_size"]
        if op_category == "Read":
            stats[bucket]["read_ios"] += 1
            stats[bucket]["read_kb"] += io_size / 1024
            stats[bucket]["read_req_size"] += io_size
        elif op_category == "Write":
            stats[bucket]["write_ios"] += 1
            stats[bucket]["write_kb"] += io_size / 1024
            stats[bucket]["write_req_size"] += io_size

    for record in all_records:
        io_action = record["io_type"]
        op_category = get_op_type(record["op_type"])
        if io_action == "D":
            add_pending_range(pending_dispatch, op_category, {
                "timestamp": record["timestamp"],
                "lba": record["lba"],
                "block_count": record["block_count"],
            })
        elif io_action == "C":
            dispatches = match_pending_range(pending_dispatch, op_category, record["lba"], record["block_count"])
            if selected_count_record(record):
                add_stat(record)
                if dispatches:
                    start = min(dispatch["timestamp"] for dispatch in dispatches)
                    service_time = record["timestamp"] - start
                    service_times.append((get_bucket(record["timestamp"]), service_time))

    bucket_service_sum = {}
    bucket_count = {}
    for bucket, st in service_times:
        bucket_service_sum[bucket] = bucket_service_sum.get(bucket, 0.0) + st
        bucket_count[bucket] = bucket_count.get(bucket, 0) + 1

    print(f"{'Time':>8} {'Read/s':>10} {'Write/s':>10} {'Req/s':>10} {'Read BW':>12} {'Write BW':>12} {'AvgQ':>8} {'ReadReq':>10} {'WriteReq':>10} {'Util':>8}")
    print(f"{'-' * 8:>8} {'-' * 10:>10} {'-' * 10:>10} {'-' * 10:>10} {'-' * 12:>12} {'-' * 12:>12} {'-' * 8:>8} {'-' * 10:>10} {'-' * 10:>10} {'-' * 8:>8}")
    for bucket in sorted(stats.keys()):
        stat = stats[bucket]
        read_ios = stat["read_ios"]
        write_ios = stat["write_ios"]
        read_kb = stat["read_kb"]
        write_kb = stat["write_kb"]
        total_ios = read_ios + write_ios
        avg_service_time = bucket_service_sum.get(bucket, 0.0) / max(bucket_count.get(bucket, 1), 1)
        avg_qdepth = total_ios * avg_service_time
        util = min(avg_qdepth * 100, 100.0)
        read_avg_req_kb = (stat["read_req_size"] / 1024 / read_ios) if read_ios else 0.0
        write_avg_req_kb = (stat["write_req_size"] / 1024 / write_ios) if write_ios else 0.0
        print(f"{str(bucket) + 's':>8} {read_ios:>10.2f} {write_ios:>10.2f} {total_ios:>10.2f} {format_rate_kb(read_kb):>12} {format_rate_kb(write_kb):>12} {avg_qdepth:>8.2f} {format_size_kb(read_avg_req_kb):>10} {format_size_kb(write_avg_req_kb):>10} {util:>7.2f}%")

def analyze_blktrace(input_lines, filter_arg=None, by_process=False, show_latency=False):
    io_stats = {}
    pending_insert = {}
    last_lba_by_op = {}
    last_lba_by_op_fallback = {}
    overall_stats = {}

    def ensure_stats(io_size, op_category):
        if io_size not in io_stats:
            io_stats[io_size] = {}
        if op_category not in io_stats[io_size]:
            if by_process:
                io_stats[io_size][op_category] = {}
            else:
                io_stats[io_size][op_category] = {
                    "sequential": 0,
                    "random": 0,
                    "sequential_latencies": [],
                    "random_latencies": [],
                }

    def add_io(record, io_class, command_name, service_us=None):
        io_size = record["io_size"]
        op_category = get_op_type(record["op_type"])
        ensure_stats(io_size, op_category)
        proc_name = get_process_name(command_name)
        if by_process:
            if proc_name not in io_stats[io_size][op_category]:
                io_stats[io_size][op_category][proc_name] = {"sequential": 0, "random": 0, "sequential_latencies": [], "random_latencies": []}
            io_stats[io_size][op_category][proc_name][io_class] += 1
            if service_us is not None:
                io_stats[io_size][op_category][proc_name][f"{io_class}_latencies"].append(service_us)
        else:
            op_stats = io_stats[io_size][op_category]
            op_stats[io_class] += 1
            if service_us is not None:
                op_stats[f"{io_class}_latencies"].append(service_us)
        if op_category not in overall_stats:
            overall_stats[op_category] = {"sequential": 0, "random": 0}
        overall_stats[op_category][io_class] += 1

    for line in input_lines:
        record = parse_blktrace_line(line)
        if record is None or record["io_size"] == 0:
            continue

        timestamp = record["timestamp"]
        command_name = record["command_name"]
        io_action = record["io_type"]
        op_category = get_op_type(record["op_type"])
        lba = record["lba"]
        block_count = record["block_count"]

        if io_action == "D":
            io_class = classify_io(last_lba_by_op.get(op_category), lba)
            last_lba_by_op[op_category] = lba + block_count
            if show_latency:
                add_pending_range(pending_insert, op_category, {
                    "timestamp": timestamp,
                    "command_name": command_name,
                    "lba": lba,
                    "block_count": block_count,
                    "io_class": io_class,
                    "op_type": record["op_type"],
                    "io_size": record["io_size"],
                })
            add_io(record, io_class, command_name)
            continue

        if show_latency and io_action == "C":
            dispatch_items = match_pending_range(pending_insert, op_category, lba, block_count)
            if dispatch_items:
                earliest_dispatch = min(dispatch_items, key=lambda item: item["timestamp"])
                service_us = (timestamp - earliest_dispatch["timestamp"]) * 1000000
                item_op_type = get_op_type(earliest_dispatch.get("op_type", record["op_type"]))
                io_size = earliest_dispatch.get("io_size")
                io_class = earliest_dispatch.get("io_class", "random")
                if io_size and io_size in io_stats and item_op_type in io_stats[io_size]:
                    io_stats[io_size][item_op_type][f"{io_class}_latencies"].append(service_us)

    # 计算总 IO 数
    grand_total_io = sum(stats["sequential"] + stats["random"] for stats in overall_stats.values())
    if grand_total_io == 0:
        print("No valid IO records found.")
        return

    # 处理筛选
    percentage = parse_percentage_filter(filter_arg)
    count_threshold = parse_count_filter(filter_arg)
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
            if percentage is not None:
                # 百分比大于某个值：例如 pct>1%
                size_percent = (total_for_size / grand_total_io) * 100
                if size_percent > percentage:
                    filtered_sizes.append(size)
            elif count_threshold is not None:
                # IO 数量大于某个值：例如 count>3
                if total_for_size > count_threshold:
                    filtered_sizes.append(size)
            elif filter_arg.startswith(">"):
                # 大于某个具体值：>4096
                try:
                    threshold = int(filter_arg[1:])
                    if size > threshold:
                        filtered_sizes.append(size)
                except ValueError:
                    pass

    # 默认模式只输出 IO size 汇总表；-l/-c 保留详细输出
    if by_process or show_latency:
        for size in filtered_sizes:
            print_by_size(size, io_stats, grand_total_io, by_process, show_latency)

    # 打印 IO size 分布汇总表
    if not by_process:
        print(f"{'IO Size':>12} {'Count':>10} {'Pct':>8} {'READ Seq%':>10} {'READ Rnd%':>10} {'WRITE Seq%':>11} {'WRITE Rnd%':>11}")
        print(f"{'-' * 12:>12} {'-' * 10:>10} {'-' * 8:>8} {'-' * 10:>10} {'-' * 10:>10} {'-' * 11:>11} {'-' * 11:>11}")
        summary_total = 0
        summary_read_seq = 0
        summary_read_rnd = 0
        summary_write_seq = 0
        summary_write_rnd = 0
        for size in filtered_sizes:
            size_total = 0
            read_seq = 0
            read_rnd = 0
            write_seq = 0
            write_rnd = 0
            for op_type in io_stats[size]:
                op_stats = io_stats[size][op_type]
                op_total = op_stats["sequential"] + op_stats["random"]
                size_total += op_total
                if op_type == "Read":
                    read_seq += op_stats["sequential"]
                    read_rnd += op_stats["random"]
                elif op_type == "Write":
                    write_seq += op_stats["sequential"]
                    write_rnd += op_stats["random"]
            summary_total += size_total
            summary_read_seq += read_seq
            summary_read_rnd += read_rnd
            summary_write_seq += write_seq
            summary_write_rnd += write_rnd
            size_pct = (size_total / grand_total_io) * 100 if grand_total_io else 0
            read_seq_pct = (read_seq / size_total) * 100 if size_total else 0
            read_rnd_pct = (read_rnd / size_total) * 100 if size_total else 0
            write_seq_pct = (write_seq / size_total) * 100 if size_total else 0
            write_rnd_pct = (write_rnd / size_total) * 100 if size_total else 0
            print(f"{size:>12} {size_total:>10} {size_pct:>7.2f}% {read_seq_pct:>9.2f}% {read_rnd_pct:>9.2f}% {write_seq_pct:>10.2f}% {write_rnd_pct:>10.2f}%")
        total_pct = (summary_total / grand_total_io) * 100 if grand_total_io else 0
        total_read_seq_pct = (summary_read_seq / summary_total) * 100 if summary_total else 0
        total_read_rnd_pct = (summary_read_rnd / summary_total) * 100 if summary_total else 0
        total_write_seq_pct = (summary_write_seq / summary_total) * 100 if summary_total else 0
        total_write_rnd_pct = (summary_write_rnd / summary_total) * 100 if summary_total else 0
        print(f"{'-' * 12:>12} {'-' * 10:>10} {'-' * 8:>8} {'-' * 10:>10} {'-' * 10:>10} {'-' * 11:>11} {'-' * 11:>11}")
        print(f"{'Total':>12} {summary_total:>10} {total_pct:>7.2f}% {total_read_seq_pct:>9.2f}% {total_read_rnd_pct:>9.2f}% {total_write_seq_pct:>10.2f}% {total_write_rnd_pct:>10.2f}%")
        print()

    print(f"{'Overall Pattern':<24} {'Count':>10} {'Pct':>8}")
    print(f"{'-' * 24} {'-' * 10} {'-' * 8}")
    for op_category in ("Read", "Write", "Discard", "Other"):
        if op_category not in overall_stats:
            continue
        for io_class, label in (("sequential", "Sequential"), ("random", "Random")):
            count = overall_stats[op_category][io_class]
            if count == 0:
                continue
            pct = (count / grand_total_io) * 100
            print(f"{'Overall ' + label + ' ' + op_category:<24} {count:>10} {pct:>7.2f}%")
    print(f"{'Total IO count':<24} {grand_total_io:>10}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze block IO traces.')
    parser.add_argument('-f', '--file', help='Read blkparse output from file instead of stdin')
    parser.add_argument('--filter', help='Filter IO sizes: specific size (e.g., 4096), greater than size (e.g., >4096), percentage greater (e.g., pct>1%), or count greater (e.g., count>3)')
    parser.add_argument('-c', '--by-process', action='store_true', help='Group and summarize by process name')
    parser.add_argument('-x', '--stat', action='store_true', help='Print per-second statistics in an iostat -xm like format')
    parser.add_argument('-s', '--start', type=int, help='Start second for analysis range, inclusive')
    parser.add_argument('-e', '--end', type=int, help='End second for analysis range, inclusive')
    parser.add_argument('-l', '--latency', action='store_true', help='Print D-to-C service latency statistics')
    args = parser.parse_args()

    filter_arg = args.filter

    # 处理 filter 参数
    if filter_arg is not None and filter_arg.isdigit():
        filter_arg = int(filter_arg)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as input_file:
            input_lines = input_file.readlines()
    else:
        input_lines = sys.stdin.readlines()

    input_lines = filter_lines_by_time_range(input_lines, args.start, args.end)

    if args.stat:
        print_stat_report(input_lines, filter_arg)
    else:
        analyze_blktrace(input_lines, filter_arg, args.by_process, args.latency)