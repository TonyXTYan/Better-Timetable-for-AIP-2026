#!/bin/bash
# usage: matrix.sh <outdir>  : the whole baseline matrix, one config after another
O=${1:-$(dirname $0)/base}; mkdir -p $O; cd $(dirname $0)
for dev in d1280 p390; do for cpu in 1 4; do for saved in 0 50; do
  node measure.js --dev $dev --cpu $cpu --saved $saved --reps 5 --warm 1 --out $O > $O/$dev-${cpu}x-$saved.txt 2> $O/$dev-${cpu}x-$saved.log
  echo "$dev $cpu $saved exit $?"
done; done; done
echo ALLDONE
