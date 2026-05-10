#include "awsc.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

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

std::vector<std::string> split_csv(const std::string& text) {
    std::vector<std::string> out;
    std::string current;
    for (char ch : text) {
        if (ch == ',') {
            if (!current.empty()) {
                out.push_back(current);
            }
            current.clear();
            continue;
        }
        if (!std::isspace(static_cast<unsigned char>(ch))) {
            current.push_back(ch);
        }
    }
    if (!current.empty()) {
        out.push_back(current);
    }
    return out;
}

std::set<std::uint8_t> parse_lanes(const std::string& text) {
    std::set<std::uint8_t> lanes;
    for (const auto& item : split_csv(text)) {
        const auto value = static_cast<unsigned long>(std::stoul(item));
        if (value > 255) {
            throw std::runtime_error("lane must fit uint8");
        }
        lanes.insert(static_cast<std::uint8_t>(value));
    }
    return lanes;
}

std::filesystem::path cell_path_for_symbol(const std::filesystem::path& root, const awsc::Symbol& symbol) {
    const auto hex = awsc::symbol_to_hex(symbol);
    return root / "cells" / hex.substr(0, 2) / (hex + ".cell");
}

double offset_weight(std::int8_t offset) {
    const auto distance = std::abs(static_cast<int>(offset));
    if (distance <= 0) {
        return 0.0;
    }
    return 1.0 / static_cast<double>(distance);
}

void print_usage() {
    std::cerr
        << "anchorworks-symbol-counts commands:\n"
        << "  merge-stream --input <awss.bin> --output <root> [--generation <n>]\n"
        << "  verify --root <root>\n"
        << "  inspect --cell <cell>\n"
        << "  score --root <root> --context <hex,hex> [--top-k <n>] [--allowed-lanes <ids>]\n";
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
        if (command == "score") {
            struct Candidate {
                double score = 0.0;
                std::uint64_t observations = 0;
                std::set<awsc::Symbol> roots;
            };

            const auto root = std::filesystem::path(arg_value(argc, argv, "--root"));
            const auto context_items = split_csv(arg_value(argc, argv, "--context"));
            const auto top_k = static_cast<std::size_t>(arg_u64(argc, argv, "--top-k", 32));
            std::set<std::uint8_t> allowed_lanes;
            try {
                allowed_lanes = parse_lanes(arg_value(argc, argv, "--allowed-lanes"));
            } catch (const std::runtime_error&) {
                allowed_lanes = {
                    awsc::LANE_CANONICAL,
                    awsc::LANE_MATH_COMPANION,
                    awsc::LANE_STRUCTURAL_COMPANION,
                    awsc::LANE_SOURCE_SPECIFIC,
                    awsc::LANE_SOURCE_LOCAL_TEMP,
                    awsc::LANE_USER_LEXICON,
                };
            }

            std::map<awsc::Symbol, Candidate> candidates;
            std::size_t loaded_context = 0;
            for (const auto& item : context_items) {
                const auto symbol = awsc::symbol_from_hex(item);
                const auto cell_path = cell_path_for_symbol(root, symbol);
                if (!std::filesystem::exists(cell_path)) {
                    continue;
                }
                const auto cell = awsc::read_cell(cell_path);
                ++loaded_context;
                for (const auto& relation : cell.relations) {
                    if (!allowed_lanes.empty() && allowed_lanes.count(relation.lane) == 0) {
                        continue;
                    }
                    const auto weight = offset_weight(relation.offset);
                    if (weight <= 0.0) {
                        continue;
                    }
                    auto& candidate = candidates[relation.neighbor];
                    candidate.score += static_cast<double>(relation.count) * weight;
                    candidate.observations += relation.count;
                    candidate.roots.insert(symbol);
                }
            }

            std::vector<std::pair<awsc::Symbol, Candidate>> ranked(candidates.begin(), candidates.end());
            std::sort(ranked.begin(), ranked.end(), [](const auto& left, const auto& right) {
                if (left.second.score != right.second.score) return left.second.score > right.second.score;
                if (left.second.roots.size() != right.second.roots.size()) return left.second.roots.size() > right.second.roots.size();
                return left.first < right.first;
            });
            if (ranked.size() > top_k) {
                ranked.resize(top_k);
            }

            std::cout << "{"
                      << "\"ok\":true,"
                      << "\"command\":\"score\","
                      << "\"context_count\":" << loaded_context << ","
                      << "\"candidate_count\":" << candidates.size() << ","
                      << "\"candidates\":[";
            bool first = true;
            for (const auto& [symbol, candidate] : ranked) {
                if (!first) {
                    std::cout << ",";
                }
                first = false;
                std::cout << "{"
                          << "\"symbol\":\"" << awsc::symbol_to_hex(symbol) << "\","
                          << "\"score\":" << candidate.score << ","
                          << "\"observations\":" << candidate.observations << ","
                          << "\"supporting_roots\":" << candidate.roots.size()
                          << "}";
            }
            std::cout << "]}\n";
            return 0;
        }
        print_usage();
        return 2;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}
