# repo: blkutils
scripts for block device IO analysis


## print histogram of block sizes from a blkparse outputfile
```
$ grep 'C' output.txt | ./blkhist.awk
block_size  	count     	pct.
==================================================
65535       	2         	0.00%
65536       	77328     	100.00%
```

## print random/sequential IO pattern from a blkparse outputfile
```
$ grep -w 'C' output.txt | python3 blk_analyzer.py
IO Size: 65535 bytes
  Sequential IO: 2 (100.00%)
  Random IO: 0 (0.00%)

IO Size: 65536 bytes
  Sequential IO: 70836 (91.60%)
  Random IO: 6492 (8.40%)

Overall Sequential IO: 70838 (91.60%)
Overall Random IO: 6492 (8.40%)
```