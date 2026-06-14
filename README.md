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

## print IO size and pattern from a blkparse output file
By default, `blk_analyzer.py` uses `D` events for fast issued IO size and random/sequential distribution. Random/sequential pattern is classified from `D` events by operation type.

```
$ python3 blk_analyzer.py -f output.txt
     IO Size      Count      Pct  READ Seq%  READ Rnd%  WRITE Seq%  WRITE Rnd%
------------ ---------- -------- ---------- ---------- ----------- -----------
        4096       5161   18.98%      0.10%      7.23%      59.83%      32.84%
        8192       9052   33.30%      0.02%     98.72%       0.34%       0.92%
------------ ---------- -------- ---------- ---------- ----------- -----------
       Total      14213   52.28%      0.05%     65.50%      21.94%      12.51%

Overall Pattern               Count      Pct
------------------------ ---------- --------
Overall Sequential Read        1168    4.30%
Overall Random Read           14090   51.83%
Overall Sequential Write       4595   16.90%
Overall Random Write           7332   26.97%
Total IO count                27185
```

## print IO latency from a blkparse output file
Use `-l` or `--latency` to calculate D-to-C latency from `D` (dispatched to driver) and `C` (IO completion) events. This matches the time an IO spends executing on the device.

```
$ python3 blk_analyzer.py -f output.txt -l
IO Size: 4096 bytes (count: 5161, 18.98% of all IO, R:7.32%/W:92.68%)
    Pattern                 Count      Pct     LatN           min/mean/max
    ------------------ ---------- -------- -------- ----------------------
    Sequential Read             5    0.10%        5 602.30us/3.03ms/7.16ms
    Random Read               373    7.23%      373 86.19us/23.88ms/224.47ms
    Sequential Write         3088   59.83%     3088 118.46us/23.94ms/737.27ms
    Random Write             1695   32.84%     1695 108.67us/21.72ms/600.02ms
```

## filter IO sizes with blk_analyzer.py
Use the `--filter` parameter to filter IO sizes:

```bash
# filter for specific IO size
$ python3 blk_analyzer.py -f output.txt --filter 4096

# filter for IO sizes greater than a specific value
$ python3 blk_analyzer.py -f output.txt --filter ">65536"

# filter for IO sizes with percentage greater than a threshold
$ python3 blk_analyzer.py -f output.txt --filter "pct>1%"

# filter for IO sizes with count greater than a threshold
$ python3 blk_analyzer.py -f output.txt --filter "count>3"
```

## group by process with blk_analyzer.py
Use the `-c` or `--by-process` parameter to group and summarize by process name. Process names are normalized: `kworker/56:1H` becomes `kworker`, `foo:123` becomes `foo`, `workflow_75` becomes `workflow`.

```bash
# analyze IO by process
$ python3 blk_analyzer.py -f output.txt -c

# analyze IO by process with filter
$ python3 blk_analyzer.py -f output.txt -c --filter "pct>1%"
```

## print per-second statistics with blk_analyzer.py
Use the `-x` or `--stat` parameter to print per-second statistics in an `iostat -xm` like format, including read/write IOPS, bandwidth, request count, average queue depth, average request size, and utilization.

```bash
# print per-second statistics
$ python3 blk_analyzer.py -f output.txt -x

# print per-second statistics with IO size filter
$ python3 blk_analyzer.py -f output.txt -x --filter "pct>1%"

# print per-second statistics for second 10 to second 20
$ python3 blk_analyzer.py -f output.txt -x -s 10 -e 20
```

Notes:

- IOPS and bandwidth are calculated from `C` (completion) events, matching iostat's completed IO statistics.
- Average queue depth (`AvgQ`) is calculated using Little's Law: `AvgQ = IOPS × avg_service_time`.
- Utilization (`Util`) is derived from `AvgQ`: `Util = min(100, AvgQ × 100)`.
- Service time is calculated from matched `D` (dispatch) to `C` (completion) events.