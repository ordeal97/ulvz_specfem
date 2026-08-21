# includes default Makefile from previous configuration
include Makefile

# test target
default: test_models

TEST_SRCDIR ?= .

## compilation directories
O := ./obj

OBJECTS = \
	$O/meshfem3D_par.check_module.o \
	$O/adios_manager.shared_adios_module.o \
	$O/auto_ner.shared.o \
	$O/broadcast_computed_parameters.shared.o \
	$O/count_elements.shared.o \
	$O/count_points.shared.o \
	$O/define_all_layers.shared.o \
	$O/euler_angles.shared.o \
	$O/exit_mpi.shared.o \
	$O/flush_system.shared.o \
	$O/get_model_parameters.shared.o \
	$O/get_timestep_and_layers.shared.o \
	$O/init_openmp.shared.o \
	$O/parallel.sharedmpi.o \
	$O/param_reader.cc.o \
	$O/read_compute_parameters.shared.o \
	$O/read_parameter_file.shared.o \
	$O/read_value_parameters.shared.o \
	$O/shared_par.shared_module.o \
	$O/reduce.shared.o \
	$O/rthetaphi_xyz.shared.o \
	$(EMPTY_MACRO)

S40RTS_ULVZ_OBJECTS = \
	$(OBJECTS) \
	$O/lgndr.check.o \
	$O/model_ulvz.check_module.o \
	$O/model_s40rts.check.o \
	$(EMPTY_MACRO)

ULVZ_OBJECTS = \
	$(OBJECTS) \
	$O/model_ulvz.check_module.o \
	$(EMPTY_MACRO)

PREM_ULVZ_AUDIT_OBJECTS = \
	$(ULVZ_OBJECTS) \
	$O/model_prem.shared.o \
	$(EMPTY_MACRO)

test_models:
	${MPIFCCOMPILE_CHECK} ${FCFLAGS_f90} -o ./bin/test_models $(TEST_SRCDIR)/test_models.f90 -I./obj $(OBJECTS) $(MPILIBS)

test_s40rts_ulvz:
	${MPIFCCOMPILE_CHECK} ${FCFLAGS_f90} -o ./bin/test_s40rts_ulvz $(TEST_SRCDIR)/test_s40rts_ulvz.f90 -I./obj $(S40RTS_ULVZ_OBJECTS) $(MPILIBS)

ulvz_parameter_failures:
	${MPIFCCOMPILE_CHECK} ${FCFLAGS_f90} -o ./bin/test_ulvz_parameter_failures $(TEST_SRCDIR)/test_ulvz_parameter_failures.f90 -I./obj $(ULVZ_OBJECTS) $(MPILIBS)

audit_prem_ulvz_materials:
	${MPIFCCOMPILE_CHECK} ${FCFLAGS_f90} -o ./bin/audit_prem_ulvz_materials $(TEST_SRCDIR)/audit_prem_ulvz_materials.f90 -I./obj $(PREM_ULVZ_AUDIT_OBJECTS) $(MPILIBS)

inspect_s40rts_ulvz_database:
	${MPIFCCOMPILE_CHECK} ${FCFLAGS_f90} -o ./bin/inspect_s40rts_ulvz_database $(TEST_SRCDIR)/inspect_s40rts_ulvz_database.f90 -I./obj $(OBJECTS) $(MPILIBS)
