cmake_minimum_required(VERSION 3.20)
project(ygopro-engine LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ygopro-core 源码路径
set(YGOPRO_CORE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../ygopro-core")

# ocgcore 静态库 (已编译)
add_library(ocgcore STATIC IMPORTED)
set_target_properties(ocgcore PROPERTIES
    IMPORTED_LOCATION "${YGOPRO_CORE_DIR}/build/libocgcore.a"
    INTERFACE_INCLUDE_DIRECTORIES "${YGOPRO_CORE_DIR}"
)

# nlohmann/json (单头文件)
set(NLOHMANN_JSON_INCLUDE "${CMAKE_CURRENT_SOURCE_DIR}/deps/nlohmann/include")

# sqlite3 (amalgamation, compiled as C)
add_library(sqlite3 STATIC
    deps/sqlite3/sqlite3.c
)
target_include_directories(sqlite3 PUBLIC deps/sqlite3)
target_compile_definitions(sqlite3 PRIVATE
    SQLITE_THREADSAFE=0
    SQLITE_OMIT_LOAD_EXTENSION
    SQLITE_OMIT_DEPRECATED
)

# Engine 可执行文件
add_executable(ygopro-engine
    src/main.cpp
    src/bridge.cpp
    src/protocol.cpp
)

target_include_directories(ygopro-engine PRIVATE
    src
    ${YGOPRO_CORE_DIR}
    ${NLOHMANN_JSON_INCLUDE}
    deps/sqlite3
)

target_link_libraries(ygopro-engine PRIVATE
    ocgcore
    sqlite3
)

# Windows 需要链接的系统库
if(WIN32)
    target_compile_definitions(ygopro-engine PRIVATE NOMINMAX)
    target_link_libraries(ygopro-engine PRIVATE
        ws2_32
        winmm
    )
endif()
