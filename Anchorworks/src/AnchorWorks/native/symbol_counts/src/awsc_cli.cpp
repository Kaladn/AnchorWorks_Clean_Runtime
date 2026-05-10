#include "awsc.h"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace awsc = anchorworks::awsc;

namespace {

std::string arg_value(int argc, char** argv, const std::string& name) {
    for (int i = 2; i + 1 < argc; ++i) {
        if (argv[i] == name) {
            return argv[i + 1];
        }
    }
    throw std::runtime_error("missing required argument: " + name);
}

std::uint64_t arg_u64(int argc, char** argv, const std::string& name, std::uint64_t fallback) {
    for (int i = 2; i + 1 < argc; ++i) {
        if (argv[i] == name) {
            return static_cast<std::uint64_t>(std::stoull(argv[i + 1]));
        }
    }
    return fallback;
}

void print_usage() {
    std::cerr
        << "anchorworks-symbol-counts commands:\n"
        << "  merge-stream --input <awss.bin> --output <root> [--generation <n>]\n"
        << "  verify --root <root>\n"
        << "  inspect --cell <cell>\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        print_usage();
        return 2;
    }
    try {
        const std::string command = argv[1];
        if (command == "merge-stream") {
            const auto input = std::filesystem::path(arg_value(argc, argv, "--input"));
            const auto output = std::filesystem::path(arg_value(argc, argv, "--output"));
            const auto generation = arg_u64(argc, argv, "--generation", 0);
            awsc::merge_stream_to_cells(input, output, generation);
            std::cout << "{\"ok\":true,\"command\":\"merge-stream\"}\n";
            return 0;
        }
        if (command == "verify") {
            const auto root = std::filesystem::path(arg_value(argc, argv, "--root"));
            const auto result = awsc::verify_root(root);
            std::cout << "{\"ok\":" << (result.errors.empty() ? "true" : "false")
                      << ",\"checked\":" << result.checked
                      << ",\"error_count\":" << result.errors.size() << "}\n";
            for (const auto& error : result.errors) {
                std::cerr << error << "\n";
            }
            return result.errors.empty() ? 0 : 1;
        }
        if (command == "inspect") {
            const auto path = std::filesystem::path(arg_value(argc, argv, "--cell"));
            const auto cell = awsc::read_cell(path);
            std::cout << "{"
                      << "\"ok\":true,"
                      << "\"symbol\":\"" << awsc::symbol_to_hex(cell.root) << "\","
                      << "\"root_lane\":" << static_cast<int>(cell.root_lane) << ","
                      << "\"generation\":" << cell.generation << ","
                      << "\"relation_count\":" << cell.relations.size()
                      << "}\n";
            return 0;
        }
        print_usage();
        return 2;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}
