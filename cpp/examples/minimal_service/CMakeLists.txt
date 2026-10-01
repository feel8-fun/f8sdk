add_executable(f8_minimal_service main.cpp)
target_link_libraries(f8_minimal_service PRIVATE f8cppsdk Threads::Threads)
