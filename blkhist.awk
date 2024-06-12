#!/usr/bin/gawk -f
#
# print a statistics of block sizes, counts, and percentage from a blkparse output
# record format: "%5T.%9t, %p, %C, %a, %S, %n, %N\n"
# record example:
#     13.096319728, 201852, reactor_0, Q, 9868288, 128, 65536
#

BEGIN {
    FS=", ";
    printf "%-12s\t%-10s\t%-10s\n", \
           "block_size", "count", "pct."
    for(c=0;c<50;c++) printf "="; printf "\n"
};

{
    if ($7 ~ /[0-9]+$/)
    {
        a[$7] += 1; total += 1;
    }
};

END {
    for (i in a) {
        printf ("%-12s\t%-10s\t%.2f%%\n", i, a[i], 100*a[i]/total) | "sort -nk1";
    }
}
