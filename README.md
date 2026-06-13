# repo: blkutils
scripts for block device IO analysis


## collect data
```bash
# trace block io for 60s
blktrace -d /dev/nvmeXn1 -w 60

# parse trace files
blkparse nvmeXn1 -f "%5T.%9t, %p, %C, %a, %3d, %S, %n, %N\n"  -o output.txt
```

## print histogram of block sizes from a blkparse output file
```
$ grep 'C' output.txt | ./blkhist.awk
block_size  	count     	pct.
==================================================
65535       	2         	0.00%
65536       	77328     	100.00%
```

## print random/sequential IO pattern from a blkparse output file
```
$ grep -w 'D,' output.txt | python3 blk_analyzer.py
IO Size: 65535 bytes
  Sequential IO: 2 (100.00%)
  Random IO: 0 (0.00%)

IO Size: 65536 bytes
  Sequential IO: 70836 (91.60%)
  Random IO: 6492 (8.40%)

Overall Sequential IO: 70838 (91.60%)
Overall Random IO: 6492 (8.40%)
Total IO count: 77330
```

## filter IO sizes with blk_analyzer.py
Use the `--filter` parameter to filter IO sizes:

```bash
# filter for specific IO size
$ grep -w 'D,' output.txt | python3 blk_analyzer.py --filter 4096

# filter for IO sizes greater than a specific value
$ grep -w 'D,' output.txt | python3 blk_analyzer.py --filter ">65536"

# filter for IO sizes with percentage greater than a threshold
$ grep -w 'D,' output.txt | python3 blk_analyzer.py --filter "percentage>10"
```

## group by process with blk_analyzer.py
Use the `-c` or `--by-process` parameter to group and summarize by process name:

```bash
# analyze IO by process
$ grep -w 'D,' output.txt | python3 blk_analyzer.py -c

# analyze IO by process with filter
$ grep -w 'D,' output.txt | python3 blk_analyzer.py -c --filter "percentage>10"
```

## print per-second statistics with blk_analyzer.py
Use the `-s` or `--stat` parameter to print per-second statistics in an `iostat -xm` like format, including read/write IOPS, bandwidth, request count, average queue depth, average request size, and utilization.

```bash
# print per-second completed IOPS and bandwidth
$ grep -w 'C,' output.txt | python3 blk_analyzer.py -s

# print per-second issued IOPS and bandwidth
$ grep -w 'D,' output.txt | python3 blk_analyzer.py --stat

# keep both D and C events to estimate average queue depth
$ grep -E ', (D|C),' output.txt | python3 blk_analyzer.py -s

# print per-second statistics with IO size filter
$ grep -E ', (D|C),' output.txt | python3 blk_analyzer.py -s --filter "percentage>10"
```

Notes:

- Use `C` events for completed IOPS and bandwidth.
- Use `D` events for requests issued to the driver/device.
- Keep both `D` and `C` events if you want `aqu-sz` to approximate average queue depth.
- If only `D` events are provided, `aqu-sz` shows the number of requests seen in each second, not true average queue depth.