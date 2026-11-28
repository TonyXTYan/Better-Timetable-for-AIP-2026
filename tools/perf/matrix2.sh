#!/bin/bash
# usage: matrix2.sh <outdir> <hold> <cast> [dev...]  : the matrix (5 reps + 1 warm-up), one config after another,
#   with measure.js --hold/--cast; devs default to d1280 p390
O=$1; H=${2:-0}; C=${3:-0}; shift 3; DEVS=${@:-d1280 p390}; mkdir -p $O; cd $(dirname $0)
for dev in $DEVS; do for cpu in 1 4; do for saved in 0 50; do
  n=$dev-${cpu}x-$saved$([ "$H" != 0 ] && echo -h$H)
  node measure.js --dev $dev --cpu $cpu --saved $saved --reps 5 --warm 1 --hold $H --cast $C --out $O > $O/$n.txt 2> $O/$n.log
  echo "$dev $cpu $saved hold $H cast $C exit $?"
done; done; done
echo ALLDONE
