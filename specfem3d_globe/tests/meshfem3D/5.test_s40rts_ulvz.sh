#!/bin/bash
testdir=`pwd`

# executable
var=test_s40rts_ulvz

if [ -z "${ROOT}" ]; then export ROOT=../../ ; fi

cleanup() {
  rm -f $testdir/error.log
  rm -f $testdir/fort.42
  rm -f $testdir/DATA/Par_file
  rm -f $testdir/DATA/ulvz_s40rts.par
}
trap cleanup EXIT

# title
echo >> $testdir/results.log
echo "test: $var" >> $testdir/results.log
echo >> $testdir/results.log

echo "directory: `pwd`" >> $testdir/results.log

# clean
mkdir -p bin DATA

cat > DATA/Par_file <<EOF
NUMBER_OF_SIMULTANEOUS_RUNS = 1
BROADCAST_SAME_MESH_AND_MODEL = .true.
EOF

cat > DATA/ulvz_s40rts.par <<EOF
ENABLED = .true.
CENTER_LATITUDE_DEGREES = 10.0
CENTER_LONGITUDE_DEGREES = 190.0
THICKNESS_KM = 20.0
LATERAL_RADIUS_KM = 100.0
LATERAL_TAPER_KM = 20.0
TOP_TAPER_KM = 5.0
DVS = -0.20
DVP = -0.10
DRHO = 0.10
EOF

# single compilation
echo "compilation: $var" >> $testdir/results.log

if [ -f Makefile ]; then
  make -f test_models.makefile $var >> $testdir/results.log 2>&1
  exe=./bin/$var
else
  make -C $ROOT -f tests/meshfem3D/test_models.makefile \
    TEST_SRCDIR=tests/meshfem3D $var >> $testdir/results.log 2>&1
  exe=$ROOT/bin/$var
fi

echo "" >> $testdir/results.log

# check
if [ ! -e $exe ]; then
  echo "compilation of $var failed, please check..." >> $testdir/results.log
  exit 1
fi

# runs test
echo "run: `date`" >> $testdir/results.log
mpirun -np 2 $exe >> $testdir/results.log 2>$testdir/error.log

# checks exit code
if [[ $? -ne 0 ]]; then
  echo "test failed"; echo "error log:"; cat $testdir/error.log; echo ""
  exit 1
fi

# checks error output (note: fortran stop returns with a zero-exit code)
if [[ -s $testdir/error.log ]]; then
  echo "returned ERROR output:" >> $testdir/results.log
  cat $testdir/error.log >> $testdir/results.log
  exit 1
fi
rm -f $testdir/error.log

# done
echo "successfully tested: `date`" >> $testdir/results.log
