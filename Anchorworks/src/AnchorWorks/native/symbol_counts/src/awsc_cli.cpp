#include "awsc.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <regex>
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

std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot open file for reading: " + path.string());
    }
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

void write_text_file(const std::filesystem::path& path, const std::string& text) {
    std::filesystem::create_directories(path.parent_path());
    const auto tmp = path.string() + ".tmp";
    {
        std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error("cannot open temp file for writing: " + tmp);
        }
        out.write(text.data(), static_cast<std::streamsize>(text.size()));
        if (!out) {
            throw std::runtime_error("failed writing temp file: " + tmp);
        }
    }
    if (std::filesystem::exists(path)) {
        std::filesystem::remove(path);
    }
    std::filesystem::rename(tmp, path);
}

void append_u64_le(std::vector<std::uint8_t>& data, std::uint64_t value) {
    for (int i = 0; i < 8; ++i) {
        data.push_back(static_cast<std::uint8_t>((value >> (8 * i)) & 0xff));
    }
}

std::uint8_t lane_for_authority(const std::string& authority) {
    std::string normalized;
    normalized.reserve(authority.size());
    for (char ch : authority) {
        normalized.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    }
    if (normalized == "canonical") {
        return awsc::LANE_CANONICAL;
    }
    if (normalized == "math_companion") {
        return awsc::LANE_MATH_COMPANION;
    }
    if (normalized == "structural_companion") {
        return awsc::LANE_STRUCTURAL_COMPANION;
    }
    if (normalized == "user_lexicon") {
        return awsc::LANE_USER_LEXICON;
    }
    return awsc::LANE_SOURCE_LOCAL_TEMP;
}

std::string json_escape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char ch : value) {
        switch (ch) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(ch) < 0x20) {
                    out += ' ';
                } else {
                    out.push_back(ch);
                }
        }
    }
    return out;
}

struct AuthorityEntry {
    awsc::Symbol symbol{};
    std::uint8_t lane = awsc::LANE_SOURCE_LOCAL_TEMP;
};

std::string object_value(const std::string& object, const std::string& key) {
    const std::regex pattern("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return "";
    }
    return match[1].str();
}

std::map<std::string, AuthorityEntry> read_authority_snapshot(const std::filesystem::path& path) {
    const auto text = read_text_file(path);
    std::map<std::string, AuthorityEntry> authority;
    const std::regex object_pattern("\\{[^{}]*\"anchor\"[^{}]*\\}");
    for (std::sregex_iterator it(text.begin(), text.end(), object_pattern), end; it != end; ++it) {
        const auto object = it->str();
        auto anchor = object_value(object, "anchor");
        const auto symbol = object_value(object, "symbol");
        const auto auth = object_value(object, "authority");
        if (anchor.empty() || symbol.empty()) {
            continue;
        }
        std::transform(anchor.begin(), anchor.end(), anchor.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        authority[anchor] = AuthorityEntry{awsc::symbol_from_hex(symbol), lane_for_authority(auth)};
    }
    return authority;
}

std::vector<std::string> split_paragraphs_native(const std::string& text) {
    std::vector<std::string> paragraphs;
    std::string current;
    bool pending_blank = false;
    bool line_has_text = false;
    for (std::size_t index = 0; index <= text.size(); ++index) {
        const char ch = index < text.size() ? text[index] : '\n';
        if (ch == '\r') {
            continue;
        }
        if (ch == '\n') {
            if (line_has_text) {
                current.push_back('\n');
                line_has_text = false;
                pending_blank = false;
            } else if (!current.empty()) {
                pending_blank = true;
            }
            continue;
        }
        if (std::isspace(static_cast<unsigned char>(ch))) {
            if (!pending_blank) {
                current.push_back(ch);
            }
            continue;
        }
        if (pending_blank && !current.empty()) {
            while (!current.empty() && std::isspace(static_cast<unsigned char>(current.back()))) {
                current.pop_back();
            }
            if (!current.empty()) {
                paragraphs.push_back(current);
            }
            current.clear();
            pending_blank = false;
        }
        current.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
        line_has_text = true;
    }
    while (!current.empty() && std::isspace(static_cast<unsigned char>(current.back()))) {
        current.pop_back();
    }
    if (!current.empty()) {
        paragraphs.push_back(current);
    }
    return paragraphs;
}

std::vector<std::string> extract_anchors_native(const std::string& text) {
    std::vector<std::string> anchors;
    std::size_t index = 0;
    while (index < text.size()) {
        const auto ch = static_cast<unsigned char>(text[index]);
        if (std::isspace(ch)) {
            ++index;
            continue;
        }
        if (std::isalpha(ch) || text[index] == '\'') {
            std::string word;
            while (index < text.size()) {
                const auto current = static_cast<unsigned char>(text[index]);
                if (!std::isalpha(current) && text[index] != '\'') {
                    break;
                }
                word.push_back(static_cast<char>(std::tolower(current)));
                ++index;
            }
            if (!word.empty() && word.find_first_not_of('\'') != std::string::npos) {
                anchors.push_back(word);
            }
            continue;
        }
        if (std::isdigit(ch)) {
            anchors.emplace_back(1, text[index]);
            ++index;
            continue;
        }
        anchors.emplace_back(1, static_cast<char>(std::tolower(ch)));
        ++index;
    }
    return anchors;
}

void append_awss_record(
    std::vector<std::uint8_t>& data,
    const awsc::Symbol& root,
    const awsc::Symbol& neighbor,
    std::int8_t offset,
    std::uint8_t lane,
    std::uint8_t root_lane,
    std::uint64_t count
) {
    data.insert(data.end(), root.begin(), root.end());
    data.insert(data.end(), neighbor.begin(), neighbor.end());
    data.push_back(static_cast<std::uint8_t>(offset));
    data.push_back(lane);
    data.push_back(0);
    data.push_back(root_lane);
    data.push_back(0);
    data.push_back(0);
    append_u64_le(data, count);
}

struct RelationKey {
    awsc::Symbol root{};
    awsc::Symbol neighbor{};
    std::int8_t offset = 0;
    std::uint8_t lane = 0;
    std::uint8_t root_lane = 0;

    bool operator<(const RelationKey& other) const {
        if (root != other.root) return root < other.root;
        if (neighbor != other.neighbor) return neighbor < other.neighbor;
        if (offset != other.offset) return offset < other.offset;
        if (lane != other.lane) return lane < other.lane;
        return root_lane < other.root_lane;
    }
};

int run_intake_text(int argc, char** argv) {
    const auto input = std::filesystem::path(arg_value(argc, argv, "--input"));
    const auto authority_path = std::filesystem::path(arg_value(argc, argv, "--authority"));
    const auto output = std::filesystem::path(arg_value(argc, argv, "--output"));
    const auto manifest = std::filesystem::path(arg_value(argc, argv, "--manifest"));
    const auto missing_path = std::filesystem::path(arg_value(argc, argv, "--missing"));
    const auto window_radius_u64 = arg_u64(argc, argv, "--window-radius", 6);
    if (window_radius_u64 == 0 || window_radius_u64 > 127) {
        throw std::runtime_error("window radius must be 1..127");
    }
    const auto window_radius = static_cast<int>(window_radius_u64);
    const auto authority = read_authority_snapshot(authority_path);
    const auto paragraphs = split_paragraphs_native(read_text_file(input));

    std::map<RelationKey, std::uint64_t> relations;
    std::map<std::string, std::uint64_t> missing;
    std::uint64_t countable_observations = 0;
    std::uint64_t total_anchors = 0;

    for (const auto& paragraph : paragraphs) {
        const auto anchors = extract_anchors_native(paragraph);
        total_anchors += anchors.size();
        std::vector<const AuthorityEntry*> resolved;
        resolved.reserve(anchors.size());
        for (const auto& anchor : anchors) {
            const auto found = authority.find(anchor);
            if (found == authority.end()) {
                missing[anchor] += 1;
                resolved.push_back(nullptr);
            } else {
                ++countable_observations;
                resolved.push_back(&found->second);
            }
        }
        for (std::size_t position = 0; position < resolved.size(); ++position) {
            const auto* root = resolved[position];
            if (root == nullptr) {
                continue;
            }
            for (int offset = -window_radius; offset <= window_radius; ++offset) {
                if (offset == 0) {
                    continue;
                }
                const auto neighbor_index = static_cast<int>(position) + offset;
                if (neighbor_index < 0 || neighbor_index >= static_cast<int>(resolved.size())) {
                    continue;
                }
                const auto* neighbor = resolved[static_cast<std::size_t>(neighbor_index)];
                if (neighbor == nullptr) {
                    continue;
                }
                relations[RelationKey{
                    root->symbol,
                    neighbor->symbol,
                    static_cast<std::int8_t>(offset),
                    neighbor->lane,
                    root->lane,
                }] += 1;
            }
        }
    }

    std::vector<std::uint8_t> stream;
    stream.reserve(relations.size() * 24);
    std::uint64_t observation_count = 0;
    for (const auto& [key, count] : relations) {
        append_awss_record(stream, key.root, key.neighbor, key.offset, key.lane, key.root_lane, count);
        observation_count += count;
    }
    std::filesystem::create_directories(output.parent_path());
    {
        std::ofstream out(output, std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error("cannot open AWSS output for writing: " + output.string());
        }
        out.write(reinterpret_cast<const char*>(stream.data()), static_cast<std::streamsize>(stream.size()));
        if (!out) {
            throw std::runtime_error("failed writing AWSS output: " + output.string());
        }
    }

    std::string missing_json = "{\"schema_version\":\"anchorworks_native_intake_missing@1\",\"missing\":[";
    bool first_missing = true;
    for (const auto& [anchor, observations] : missing) {
        if (!first_missing) {
            missing_json += ",";
        }
        first_missing = false;
        missing_json += "{\"anchor\":\"" + json_escape(anchor) + "\",\"observations\":" + std::to_string(observations) + "}";
    }
    missing_json += "]}";
    write_text_file(missing_path, missing_json);

    const auto manifest_json =
        std::string("{\"schema_version\":\"anchorworks_native_intake_manifest@1\"") +
        ",\"ok\":true" +
        ",\"input\":\"" + json_escape(input.string()) + "\"" +
        ",\"authority\":\"" + json_escape(authority_path.string()) + "\"" +
        ",\"output\":\"" + json_escape(output.string()) + "\"" +
        ",\"window_radius\":" + std::to_string(window_radius) +
        ",\"paragraph_count\":" + std::to_string(paragraphs.size()) +
        ",\"anchor_observation_count\":" + std::to_string(total_anchors) +
        ",\"countable_anchor_observation_count\":" + std::to_string(countable_observations) +
        ",\"missing_anchor_count\":" + std::to_string(missing.size()) +
        ",\"record_count\":" + std::to_string(relations.size()) +
        ",\"relation_observation_count\":" + std::to_string(observation_count) +
        ",\"record_size\":24" +
        ",\"raw_text_in_count_spine\":false}";
    write_text_file(manifest, manifest_json);

    std::cout << "{\"ok\":true,\"command\":\"intake-text\",\"record_count\":" << relations.size()
              << ",\"missing_anchor_count\":" << missing.size() << "}\n";
    return 0;
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
        << "  intake-text --input <prepared.txt> --authority <snapshot.json> --output <awss.bin> --manifest <manifest.json> --missing <missing.json> [--window-radius <n>]\n"
        << "  merge-stream --input <awss.bin> --output <root> [--generation <n>]\n"
        << "  merge-symbol-stream --input <awsy.bin> --output <root> [--generation <n>] [--window-radius <n>]\n"
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
        if (command == "intake-text") {
            return run_intake_text(argc, argv);
        }
        if (command == "merge-stream") {
            const auto input = std::filesystem::path(arg_value(argc, argv, "--input"));
            const auto output = std::filesystem::path(arg_value(argc, argv, "--output"));
            const auto generation = arg_u64(argc, argv, "--generation", 0);
            awsc::merge_stream_to_cells(input, output, generation);
            std::cout << "{\"ok\":true,\"command\":\"merge-stream\"}\n";
            return 0;
        }
        if (command == "merge-symbol-stream") {
            const auto input = std::filesystem::path(arg_value(argc, argv, "--input"));
            const auto output = std::filesystem::path(arg_value(argc, argv, "--output"));
            const auto generation = arg_u64(argc, argv, "--generation", 0);
            const auto window_radius = static_cast<std::int8_t>(arg_u64(argc, argv, "--window-radius", 6));
            awsc::merge_symbol_stream_to_cells(input, output, generation, window_radius);
            std::cout << "{\"ok\":true,\"command\":\"merge-symbol-stream\"}\n";
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
