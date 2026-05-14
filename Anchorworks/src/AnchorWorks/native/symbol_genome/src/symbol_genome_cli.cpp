#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Options {
    std::filesystem::path input;
    std::filesystem::path output;
    std::uint32_t start_index = 0;
    std::uint8_t category_code = 0;
    std::uint8_t priority = 4;
};

std::string require_value(const std::vector<std::string>& args, std::size_t& index, const std::string& flag) {
    if (index + 1 >= args.size()) {
        throw std::runtime_error("missing value for " + flag);
    }
    ++index;
    return args[index];
}

std::uint8_t category_code_for(const std::string& category) {
    if (category == "core") {
        return 0;
    }
    if (category == "specialized") {
        return 1;
    }
    if (category == "future") {
        return 2;
    }
    throw std::runtime_error("unknown category: " + category);
}

Options parse_allocate_options(const std::vector<std::string>& args) {
    Options options;
    for (std::size_t i = 2; i < args.size(); ++i) {
        const std::string& arg = args[i];
        if (arg == "--input") {
            options.input = require_value(args, i, arg);
        } else if (arg == "--output") {
            options.output = require_value(args, i, arg);
        } else if (arg == "--start-index") {
            options.start_index = static_cast<std::uint32_t>(std::stoul(require_value(args, i, arg)));
        } else if (arg == "--category") {
            options.category_code = category_code_for(require_value(args, i, arg));
        } else if (arg == "--priority") {
            const int priority = std::stoi(require_value(args, i, arg));
            if (priority < 0 || priority > 7) {
                throw std::runtime_error("priority must be 0..7");
            }
            options.priority = static_cast<std::uint8_t>(priority);
        } else {
            throw std::runtime_error("unknown argument: " + arg);
        }
    }
    if (options.input.empty()) {
        throw std::runtime_error("--input is required");
    }
    if (options.output.empty()) {
        throw std::runtime_error("--output is required");
    }
    return options;
}

std::string hex_for_symbol(const std::uint8_t bytes[5]) {
    std::ostringstream out;
    out << "0x" << std::uppercase << std::hex << std::setfill('0');
    for (int i = 0; i < 5; ++i) {
        out << std::setw(2) << static_cast<int>(bytes[i]);
    }
    return out.str();
}

std::string binary_for_symbol(const std::uint8_t bytes[5]) {
    std::string out;
    out.reserve(40);
    for (int i = 0; i < 5; ++i) {
        for (int bit = 7; bit >= 0; --bit) {
            out.push_back(((bytes[i] >> bit) & 1U) ? '1' : '0');
        }
    }
    return out;
}

void symbol_from_index(const Options& options, std::uint32_t allocation_index, std::uint8_t out[5]) {
    out[0] = static_cast<std::uint8_t>((options.category_code << 5U) | (options.priority << 2U));
    out[1] = static_cast<std::uint8_t>((allocation_index >> 24U) & 0xFFU);
    out[2] = static_cast<std::uint8_t>((allocation_index >> 16U) & 0xFFU);
    out[3] = static_cast<std::uint8_t>((allocation_index >> 8U) & 0xFFU);
    out[4] = static_cast<std::uint8_t>(allocation_index & 0xFFU);
}

int allocate(const Options& options) {
    std::ifstream input(options.input);
    if (!input) {
        throw std::runtime_error("could not open input: " + options.input.string());
    }
    std::filesystem::create_directories(options.output.parent_path());
    std::ofstream output(options.output, std::ios::trunc);
    if (!output) {
        throw std::runtime_error("could not open output: " + options.output.string());
    }

    std::string line;
    std::uint64_t line_index = 0;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        if (options.start_index + line_index > 0xFFFFFFFFULL) {
            throw std::runtime_error("symbol genome allocation index overflow");
        }
        const auto allocation_index = static_cast<std::uint32_t>(options.start_index + line_index);
        std::uint8_t symbol[5] = {0, 0, 0, 0, 0};
        symbol_from_index(options, allocation_index, symbol);
        output << line_index
               << '\t' << allocation_index
               << '\t' << hex_for_symbol(symbol)
               << '\t' << binary_for_symbol(symbol)
               << '\n';
        ++line_index;
    }

    std::cout << "{\"ok\":true,\"allocated\":" << line_index << ",\"generator\":\"native_cpp_symbol_genome_allocator\"}\n";
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::vector<std::string> args(argv, argv + argc);
        if (args.size() < 2) {
            throw std::runtime_error("command required");
        }
        if (args[1] == "allocate") {
            return allocate(parse_allocate_options(args));
        }
        throw std::runtime_error("unknown command: " + args[1]);
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }
}
