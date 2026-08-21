program test_ulvz_parameter_failures

  use constants, only: myrank
  use model_ulvz_par, only: ulvz_initialize
  use shared_parameters, only: MODEL_NAME

  implicit none

  character(len=128) :: model_name_arg

  call get_command_argument(1,model_name_arg)
  if (len_trim(model_name_arg) == 0) stop 'Usage: test_ulvz_parameter_failures MODEL_NAME'
  call init_mpi()
  call world_rank(myrank)
  MODEL_NAME = trim(model_name_arg)
  call ulvz_initialize()
  call finalize_mpi()
  stop 'Expected ULVZ parameter validation failure did not occur'

end program test_ulvz_parameter_failures
