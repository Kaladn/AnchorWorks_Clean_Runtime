#include "awsc.h"

#include <algorithm>
#include <cctype>
#include <cmath>
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

bool has_flag(int argc, char** argv, const std::string& name) {
    for (int i = 2; i < argc; ++i) {
        if (argv[i] == name) {
            return true;
        }
    }
    return false;
}

std::string optional_arg_value(int argc, char** argv, const std::string& name, const std::string& fallback) {
    for (int i = 2; i + 1 < argc; ++i) {
        if (argv[i] == name) {
            return argv[i + 1];
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

void write_u64(std::ofstream& out, std::uint64_t value) {
    out.write(reinterpret_cast<const char*>(&value), sizeof(value));
}

std::uint64_t read_u64(std::ifstream& in) {
    std::uint64_t value = 0;
    in.read(reinterpret_cast<char*>(&value), sizeof(value));
    if (!in) {
        throw std::runtime_error("failed reading native block index integer");
    }
    return value;
}

void write_index_string(std::ofstream& out, const std::string& value) {
    write_u64(out, static_cast<std::uint64_t>(value.size()));
    out.write(value.data(), static_cast<std::streamsize>(value.size()));
}

std::string read_index_string(std::ifstream& in) {
    const auto size = read_u64(in);
    std::string value(size, '\0');
    if (size > 0) {
        in.read(value.data(), static_cast<std::streamsize>(size));
        if (!in) {
            throw std::runtime_error("failed reading native block index string");
        }
    }
    return value;
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

struct IntakeStats {
    std::uint64_t paragraph_count = 0;
    std::uint64_t anchor_observation_count = 0;
    std::uint64_t countable_anchor_observation_count = 0;
};

struct AwBlock {
    std::uint64_t block_id = 0;
    std::string source_file;
    std::string doc_id;
    std::uint64_t doc_line_start = 0;
    std::uint64_t doc_line_end = 0;
    std::uint64_t block_line_start = 1;
    std::uint64_t block_line_end = 0;
    std::string text;
    std::vector<std::string> anchors;
};

std::vector<std::string> extract_anchors_native(const std::string& text);
std::vector<std::string> split_lines_preserve(const std::string& text);

std::uint64_t fnv1a_64(const std::string& text) {
    std::uint64_t hash = 14695981039346656037ULL;
    for (unsigned char ch : text) {
        hash ^= static_cast<std::uint64_t>(ch);
        hash *= 1099511628211ULL;
    }
    return hash;
}

awsc::Symbol source_local_symbol_for(const std::string& source_id, const std::string& anchor) {
    const auto hash = fnv1a_64(source_id + "\n" + anchor);
    const auto value = 0xF000000000ULL | (hash & 0x0FFFFFFFFFULL);
    awsc::Symbol symbol{};
    for (int i = 0; i < 5; ++i) {
        symbol[static_cast<std::size_t>(4 - i)] = static_cast<std::uint8_t>((value >> (8 * i)) & 0xff);
    }
    return symbol;
}

std::string object_value(const std::string& object, const std::string& key) {
    const std::regex pattern("\"" + key + "\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return "";
    }
    const auto raw = match[1].str();
    std::string out;
    out.reserve(raw.size());
    for (std::size_t index = 0; index < raw.size(); ++index) {
        const auto ch = raw[index];
        if (ch != '\\' || index + 1 >= raw.size()) {
            out.push_back(ch);
            continue;
        }
        const auto escaped = raw[++index];
        switch (escaped) {
            case '"': out.push_back('"'); break;
            case '\\': out.push_back('\\'); break;
            case '/': out.push_back('/'); break;
            case 'b': out.push_back('\b'); break;
            case 'f': out.push_back('\f'); break;
            case 'n': out.push_back('\n'); break;
            case 'r': out.push_back('\r'); break;
            case 't': out.push_back('\t'); break;
            default:
                out.push_back(escaped);
                break;
        }
    }
    return out;
}

std::vector<std::string> json_objects_containing_key(const std::string& text, const std::string& key) {
    std::vector<std::string> objects;
    bool in_string = false;
    bool escaped = false;
    std::vector<std::size_t> starts;

    for (std::size_t index = 0; index < text.size(); ++index) {
        const auto ch = text[index];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
            continue;
        }
        if (ch == '{') {
            starts.push_back(index);
            continue;
        }
        if (ch == '}' && !starts.empty()) {
            const auto object_start = starts.back();
            starts.pop_back();
            const auto object = text.substr(object_start, index - object_start + 1);
            if (object.find("\"" + key + "\"") != std::string::npos) {
                objects.push_back(object);
            }
        }
    }
    return objects;
}

std::vector<std::string> json_objects_containing_anchor(const std::string& text) {
    return json_objects_containing_key(text, "anchor");
}

std::vector<std::string> attention_variants_for_anchor(const std::string& anchor) {
    std::vector<std::string> variants{anchor};
    if (anchor == "anemia") {
        variants.push_back("anaemia");
    } else if (anchor == "anaemia") {
        variants.push_back("anemia");
    } else if (anchor == "thalassemia") {
        variants.push_back("thalassaemia");
    } else if (anchor == "thalassaemia") {
        variants.push_back("thalassemia");
    }
    return variants;
}

bool is_low_focus_anchor(const std::string& anchor) {
    static const std::set<std::string> low = {
        "all",
        "case",
        "cases",
        "count",
        "data",
        "found",
        "high",
        "increase",
        "increased",
        "level",
        "levels",
        "new",
        "result",
        "results",
        "study",
        "subjects",
        "trait",
        "using",
    };
    return low.count(anchor) > 0;
}

bool is_blocked_focus_anchor(const std::string& anchor) {
    static const std::set<std::string> blocked = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "may",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "would",
        "you",
    };
    return blocked.count(anchor) > 0;
}

double anchor_specificity_weight(const std::string& anchor) {
    if (is_blocked_focus_anchor(anchor)) {
        return 0.0;
    }
    if (anchor.size() <= 2) {
        return 0.05;
    }
    double weight = 1.0 + std::min<double>(static_cast<double>(anchor.size()), 18.0) / 8.0;
    if (is_low_focus_anchor(anchor)) {
        weight *= 0.35;
    }
    return weight;
}

double anchor_rarity_weight(
    const std::string& anchor,
    const std::map<std::string, std::uint64_t>& block_frequency,
    std::uint64_t block_count
) {
    const auto found = block_frequency.find(anchor);
    const auto frequency = found == block_frequency.end() ? 0.0 : static_cast<double>(found->second);
    return 1.0 + std::log((static_cast<double>(block_count) + 1.0) / (frequency + 1.0));
}

std::uint64_t object_u64(const std::string& object, const std::string& key) {
    const std::regex pattern("\"" + key + "\"\\s*:\\s*([0-9]+)");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return 0;
    }
    return static_cast<std::uint64_t>(std::stoull(match[1].str()));
}

std::vector<std::string> object_string_array(const std::string& object, const std::string& key) {
    std::vector<std::string> values;
    const std::regex pattern("\"" + key + "\"\\s*:\\s*\\[(.*?)\\]");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return values;
    }
    const auto array_text = match[1].str();
    const std::regex item_pattern("\"((?:\\\\.|[^\"\\\\])*)\"");
    for (auto it = std::sregex_iterator(array_text.begin(), array_text.end(), item_pattern);
         it != std::sregex_iterator();
         ++it) {
        values.push_back(object_value("{\"v\":\"" + (*it)[1].str() + "\"}", "v"));
    }
    return values;
}

std::map<std::string, AuthorityEntry> read_authority_snapshot(const std::filesystem::path& path) {
    const auto text = read_text_file(path);
    std::map<std::string, AuthorityEntry> authority;
    for (const auto& object : json_objects_containing_anchor(text)) {
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

std::string extract_document_id_from_block(const std::string& text) {
    const auto lines = split_lines_preserve(text);
    const std::regex pattern("^\\s*(document[_ ]?id|doc[_ ]?id)\\s*:\\s*(.+?)\\s*$", std::regex_constants::icase);
    std::smatch match;
    for (const auto& line : lines) {
        if (std::regex_match(line, match, pattern)) {
            return match[2].str();
        }
    }
    return "";
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

std::vector<std::string> split_lines_preserve(const std::string& text) {
    std::vector<std::string> lines;
    std::string current;
    for (char ch : text) {
        if (ch == '\r') {
            continue;
        }
        if (ch == '\n') {
            lines.push_back(current);
            current.clear();
            continue;
        }
        current.push_back(ch);
    }
    lines.push_back(current);
    return lines;
}

bool line_has_text(const std::string& line) {
    for (unsigned char ch : line) {
        if (!std::isspace(ch)) {
            return true;
        }
    }
    return false;
}

std::vector<AwBlock> collect_aw_blocks(const std::filesystem::path& input) {
    const auto text = read_text_file(input);
    const auto lines = split_lines_preserve(text);
    std::vector<AwBlock> blocks;
    std::vector<std::string> current_lines;
    std::uint64_t block_start_line = 0;

    auto flush = [&](std::uint64_t end_line) {
        if (current_lines.empty()) {
            return;
        }
        std::string block_text;
        for (std::size_t index = 0; index < current_lines.size(); ++index) {
            if (index > 0) {
                block_text.push_back('\n');
            }
            block_text += current_lines[index];
        }
        AwBlock block;
        block.block_id = static_cast<std::uint64_t>(blocks.size());
        block.source_file = input.filename().string();
        block.doc_id = extract_document_id_from_block(block_text);
        block.doc_line_start = block_start_line;
        block.doc_line_end = end_line;
        block.block_line_start = 1;
        block.block_line_end = static_cast<std::uint64_t>(current_lines.size());
        block.text = block_text;
        block.anchors = extract_anchors_native(block_text);
        blocks.push_back(block);
        current_lines.clear();
        block_start_line = 0;
    };

    for (std::size_t index = 0; index < lines.size(); ++index) {
        const auto line_number = static_cast<std::uint64_t>(index + 1);
        const auto& line = lines[index];
        if (!line_has_text(line)) {
            flush(line_number > 0 ? line_number - 1 : 0);
            continue;
        }
        if (current_lines.empty()) {
            block_start_line = line_number;
        }
        current_lines.push_back(line);
    }
    flush(static_cast<std::uint64_t>(lines.size()));
    return blocks;
}

std::string aw_blocks_json(const std::vector<AwBlock>& blocks) {
    std::string out = "[";
    bool first = true;
    for (const auto& block : blocks) {
        if (!first) {
            out += ",";
        }
        first = false;
        out += "{\"block_id\":" + std::to_string(block.block_id) +
               ",\"source_file\":\"" + json_escape(block.source_file) + "\"" +
               ",\"doc_id\":\"" + json_escape(block.doc_id) + "\"" +
               ",\"block_line_start\":" + std::to_string(block.block_line_start) +
               ",\"block_line_end\":" + std::to_string(block.block_line_end) +
               ",\"document_line_start\":" + std::to_string(block.doc_line_start) +
               ",\"document_line_end\":" + std::to_string(block.doc_line_end) +
               ",\"doc_line_start\":" + std::to_string(block.doc_line_start) +
               ",\"doc_line_end\":" + std::to_string(block.doc_line_end) +
               ",\"anchor_count\":" + std::to_string(block.anchors.size()) +
               ",\"anchors\":[";
        bool first_anchor = true;
        for (const auto& anchor : block.anchors) {
            if (!first_anchor) {
                out += ",";
            }
            first_anchor = false;
            out += "\"" + json_escape(anchor) + "\"";
        }
        out += "]}";
    }
    out += "]";
    return out;
}

void write_aw_markdown_copy(const std::filesystem::path& output, const std::filesystem::path& input, const std::vector<AwBlock>& blocks) {
    std::string text;
    text += "---\n";
    text += "schema_version: anchorworks_aw_md_blocks@1\n";
    text += "source_file: " + input.filename().string() + "\n";
    text += "source_path: " + input.string() + "\n";
    text += "block_count: " + std::to_string(blocks.size()) + "\n";
    text += "---\n\n";
    for (const auto& block : blocks) {
        text += "## AW Block " + std::to_string(block.block_id) + "\n\n";
        text += "source_file: " + block.source_file + "\n";
        if (!block.doc_id.empty()) {
            text += "doc_id: " + block.doc_id + "\n";
        }
        text += "block_id: " + std::to_string(block.block_id) + "\n";
        text += "block_lines: " + std::to_string(block.block_line_start) + "-" + std::to_string(block.block_line_end) + "\n";
        text += "doc_lines: " + std::to_string(block.doc_line_start) + "-" + std::to_string(block.doc_line_end) + "\n";
        text += "anchor_count: " + std::to_string(block.anchors.size()) + "\n\n";
        text += "```text\n";
        text += block.text;
        text += "\n```\n\n";
    }
    write_text_file(output, text);
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
        if (ch >= 0x80) {
            ++index;
            continue;
        }
        if (std::isalpha(ch) || text[index] == '\'') {
            std::string word;
            while (index < text.size()) {
                const auto current = static_cast<unsigned char>(text[index]);
                if (current >= 0x80) {
                    break;
                }
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

void add_text_file_to_relations(
    const std::filesystem::path& input,
    const std::map<std::string, AuthorityEntry>& authority,
    const std::string& source_id,
    bool source_local_missing,
    int window_radius,
    std::map<RelationKey, std::uint64_t>& relations,
    std::map<std::string, std::uint64_t>& missing,
    std::map<std::string, AuthorityEntry>& source_local,
    IntakeStats& stats
) {
    const auto paragraphs = split_paragraphs_native(read_text_file(input));
    stats.paragraph_count += paragraphs.size();

    for (const auto& paragraph : paragraphs) {
        const auto anchors = extract_anchors_native(paragraph);
        stats.anchor_observation_count += anchors.size();
        std::vector<AuthorityEntry> resolved;
        std::vector<bool> is_resolved;
        resolved.reserve(anchors.size());
        is_resolved.reserve(anchors.size());
        for (const auto& anchor : anchors) {
            const auto found = authority.find(anchor);
            if (found == authority.end()) {
                missing[anchor] += 1;
                if (source_local_missing) {
                    const auto local_key = source_id + "\n" + anchor;
                    auto local_found = source_local.find(local_key);
                    if (local_found == source_local.end()) {
                        local_found = source_local.emplace(
                            local_key,
                            AuthorityEntry{source_local_symbol_for(source_id, anchor), awsc::LANE_SOURCE_LOCAL_TEMP}
                        ).first;
                    }
                    ++stats.countable_anchor_observation_count;
                    resolved.push_back(local_found->second);
                    is_resolved.push_back(true);
                } else {
                    resolved.push_back(AuthorityEntry{});
                    is_resolved.push_back(false);
                }
            } else {
                ++stats.countable_anchor_observation_count;
                resolved.push_back(found->second);
                is_resolved.push_back(true);
            }
        }
        for (std::size_t position = 0; position < resolved.size(); ++position) {
            if (!is_resolved[position]) {
                continue;
            }
            const auto& root = resolved[position];
            for (int offset = -window_radius; offset <= window_radius; ++offset) {
                if (offset == 0) {
                    continue;
                }
                const auto neighbor_index = static_cast<int>(position) + offset;
                if (neighbor_index < 0 || neighbor_index >= static_cast<int>(resolved.size())) {
                    continue;
                }
                if (!is_resolved[static_cast<std::size_t>(neighbor_index)]) {
                    continue;
                }
                const auto& neighbor = resolved[static_cast<std::size_t>(neighbor_index)];
                relations[RelationKey{
                    root.symbol,
                    neighbor.symbol,
                    static_cast<std::int8_t>(offset),
                    neighbor.lane,
                    root.lane,
                }] += 1;
            }
        }
    }
}

int run_intake_text(int argc, char** argv) {
    const auto input = std::filesystem::path(arg_value(argc, argv, "--input"));
    const auto authority_path = std::filesystem::path(arg_value(argc, argv, "--authority"));
    const auto output = std::filesystem::path(arg_value(argc, argv, "--output"));
    const auto manifest = std::filesystem::path(arg_value(argc, argv, "--manifest"));
    const auto missing_path = std::filesystem::path(arg_value(argc, argv, "--missing"));
    const auto source_id = optional_arg_value(argc, argv, "--source-id", input.filename().string());
    const auto aw_md_copy = optional_arg_value(argc, argv, "--aw-md-copy", "");
    const auto source_local_missing = has_flag(argc, argv, "--source-local-missing");
    const auto window_radius_u64 = arg_u64(argc, argv, "--window-radius", 6);
    if (window_radius_u64 == 0 || window_radius_u64 > 127) {
        throw std::runtime_error("window radius must be 1..127");
    }
    const auto window_radius = static_cast<int>(window_radius_u64);
    const auto authority = read_authority_snapshot(authority_path);
    std::map<RelationKey, std::uint64_t> relations;
    std::map<std::string, std::uint64_t> missing;
    std::map<std::string, AuthorityEntry> source_local;
    const auto aw_blocks = collect_aw_blocks(input);
    IntakeStats stats;
    add_text_file_to_relations(
        input,
        authority,
        source_id,
        source_local_missing,
        window_radius,
        relations,
        missing,
        source_local,
        stats
    );

    std::uint64_t observation_count = 0;
    for (const auto& [key, count] : relations) {
        observation_count += count;
    }
    std::vector<std::uint8_t> stream;
    stream.reserve(relations.size() * 24);
    for (const auto& [key, count] : relations) {
        append_awss_record(stream, key.root, key.neighbor, key.offset, key.lane, key.root_lane, count);
    }
    std::filesystem::create_directories(output.parent_path());
    {
        std::ofstream out(output, std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error("cannot open count bin output for writing: " + output.string());
        }
        out.write(reinterpret_cast<const char*>(stream.data()), static_cast<std::streamsize>(stream.size()));
        if (!out) {
            throw std::runtime_error("failed writing count bin output: " + output.string());
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
    missing_json += "],\"source_local_symbols\":[";
    bool first_source_local = true;
    for (const auto& [local_key, entry] : source_local) {
        if (!first_source_local) {
            missing_json += ",";
        }
        first_source_local = false;
        const auto split = local_key.find('\n');
        const auto anchor = split == std::string::npos ? local_key : local_key.substr(split + 1);
        missing_json += "{\"anchor\":\"" + json_escape(anchor) +
                        "\",\"symbol\":\"0x" + awsc::symbol_to_hex(entry.symbol) +
                        "\",\"observations\":" + std::to_string(missing[anchor]) + "}";
    }
    missing_json += "]}";
    write_text_file(missing_path, missing_json);
    if (!aw_md_copy.empty()) {
        write_aw_markdown_copy(std::filesystem::path(aw_md_copy), input, aw_blocks);
    }

    const auto manifest_json =
        std::string("{\"schema_version\":\"anchorworks_native_intake_manifest@1\"") +
        ",\"ok\":true" +
        ",\"input\":\"" + json_escape(input.string()) + "\"" +
        ",\"source_file\":\"" + json_escape(input.filename().string()) + "\"" +
        ",\"source_files\":[\"" + json_escape(input.filename().string()) + "\"]" +
        ",\"authority\":\"" + json_escape(authority_path.string()) + "\"" +
        ",\"output\":\"" + json_escape(output.string()) + "\"" +
        ",\"source_id\":\"" + json_escape(source_id) + "\"" +
        ",\"window_radius\":" + std::to_string(window_radius) +
        ",\"paragraph_count\":" + std::to_string(stats.paragraph_count) +
        ",\"block_count\":" + std::to_string(aw_blocks.size()) +
        ",\"blocks\":" + aw_blocks_json(aw_blocks) +
        ",\"anchor_observation_count\":" + std::to_string(stats.anchor_observation_count) +
        ",\"countable_anchor_observation_count\":" + std::to_string(stats.countable_anchor_observation_count) +
        ",\"missing_anchor_count\":" + std::to_string(missing.size()) +
        ",\"source_local_symbol_count\":" + std::to_string(source_local.size()) +
        ",\"record_count\":" + std::to_string(relations.size()) +
        ",\"relation_observation_count\":" + std::to_string(observation_count) +
        ",\"record_size\":24" +
        ",\"raw_text_in_count_spine\":false" +
        ",\"aw_md_copy_path\":\"" + json_escape(aw_md_copy) + "\"}";
    write_text_file(manifest, manifest_json);

    std::cout << "{\"ok\":true,\"command\":\"intake-text\",\"record_count\":" << relations.size()
              << ",\"missing_anchor_count\":" << missing.size()
              << ",\"source_local_symbol_count\":" << source_local.size()
              << ",\"aw_md_copy_path\":\"" << json_escape(aw_md_copy) << "\"}\n";
    return 0;
}

std::string lower_string(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

bool is_generated_runtime_path(const std::filesystem::path& root, const std::filesystem::path& path) {
    static const std::set<std::string> names = {
        "State", "AnchorMaps", "build", "dist", "__pycache__", ".git", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", "node_modules", "outputs"
    };
    const auto relative = std::filesystem::relative(path, root);
    for (auto it = relative.begin(); it != relative.end(); ++it) {
        if (std::next(it) == relative.end()) {
            break;
        }
        if (names.count(it->string()) > 0) {
            return true;
        }
    }
    return false;
}

bool has_supported_text_suffix(const std::filesystem::path& path) {
    static const std::set<std::string> suffixes = {
        ".txt", ".md", ".rst", ".srt", ".vtt", ".json", ".jsonl", ".csv", ".tsv", ".log"
    };
    const auto ext = lower_string(path.extension().string());
    return ext.empty() || suffixes.count(ext) > 0;
}

std::string json_skipped_files(const std::vector<std::pair<std::filesystem::path, std::string>>& skipped) {
    std::string out = "[";
    bool first = true;
    for (const auto& [path, reason] : skipped) {
        if (!first) {
            out += ",";
        }
        first = false;
        out += "{\"source_path\":\"" + json_escape(path.string()) + "\",\"reason\":\"" + json_escape(reason) + "\"}";
    }
    out += "]";
    return out;
}

int run_intake_dir(int argc, char** argv) {
    const auto input_dir = std::filesystem::path(arg_value(argc, argv, "--input-dir"));
    const auto authority_path = std::filesystem::path(arg_value(argc, argv, "--authority"));
    const auto output = std::filesystem::path(arg_value(argc, argv, "--output"));
    const auto manifest = std::filesystem::path(arg_value(argc, argv, "--manifest"));
    const auto missing_path = std::filesystem::path(arg_value(argc, argv, "--missing"));
    const auto source_id_prefix = optional_arg_value(argc, argv, "--source-id", input_dir.filename().string());
    const auto source_local_missing = has_flag(argc, argv, "--source-local-missing");
    const auto window_radius_u64 = arg_u64(argc, argv, "--window-radius", 6);
    if (!std::filesystem::exists(input_dir) || !std::filesystem::is_directory(input_dir)) {
        throw std::runtime_error("input directory does not exist: " + input_dir.string());
    }
    if (window_radius_u64 == 0 || window_radius_u64 > 127) {
        throw std::runtime_error("window radius must be 1..127");
    }
    const auto window_radius = static_cast<int>(window_radius_u64);
    const auto authority = read_authority_snapshot(authority_path);

    std::vector<std::filesystem::path> files;
    std::vector<std::pair<std::filesystem::path, std::string>> skipped;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(input_dir)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        const auto path = entry.path();
        if (is_generated_runtime_path(input_dir, path)) {
            skipped.emplace_back(path, "generated_runtime_path");
            continue;
        }
        if (!has_supported_text_suffix(path)) {
            skipped.emplace_back(path, "unsupported_suffix");
            continue;
        }
        files.push_back(path);
    }
    std::sort(files.begin(), files.end());
    std::sort(skipped.begin(), skipped.end(), [](const auto& left, const auto& right) {
        return left.first.string() < right.first.string();
    });

    std::map<RelationKey, std::uint64_t> relations;
    std::map<std::string, std::uint64_t> missing;
    std::map<std::string, AuthorityEntry> source_local;
    IntakeStats stats;
    for (const auto& path : files) {
        const auto rel = std::filesystem::relative(path, input_dir).generic_string();
        add_text_file_to_relations(
            path,
            authority,
            source_id_prefix + "/" + rel,
            source_local_missing,
            window_radius,
            relations,
            missing,
            source_local,
            stats
        );
    }

    std::uint64_t observation_count = 0;
    for (const auto& [key, count] : relations) {
        observation_count += count;
    }
    std::vector<std::uint8_t> stream;
    stream.reserve(relations.size() * 24);
    for (const auto& [key, count] : relations) {
        append_awss_record(stream, key.root, key.neighbor, key.offset, key.lane, key.root_lane, count);
    }
    std::filesystem::create_directories(output.parent_path());
    {
        std::ofstream out(output, std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error("cannot open count bin output for writing: " + output.string());
        }
        out.write(reinterpret_cast<const char*>(stream.data()), static_cast<std::streamsize>(stream.size()));
        if (!out) {
            throw std::runtime_error("failed writing count bin output: " + output.string());
        }
    }

    std::string missing_json = "{\"schema_version\":\"anchorworks_native_intake_missing@1\",\"missing\":";
    missing_json += "[";
    bool first_missing = true;
    for (const auto& [anchor, observations] : missing) {
        if (!first_missing) missing_json += ",";
        first_missing = false;
        missing_json += "{\"anchor\":\"" + json_escape(anchor) + "\",\"observations\":" + std::to_string(observations) + "}";
    }
    missing_json += "],\"source_local_symbols\":[";
    bool first_source_local = true;
    for (const auto& [local_key, entry] : source_local) {
        if (!first_source_local) missing_json += ",";
        first_source_local = false;
        const auto split = local_key.find('\n');
        const auto anchor = split == std::string::npos ? local_key : local_key.substr(split + 1);
        missing_json += "{\"anchor\":\"" + json_escape(anchor) +
                        "\",\"symbol\":\"0x" + awsc::symbol_to_hex(entry.symbol) +
                        "\",\"observations\":" + std::to_string(missing[anchor]) + "}";
    }
    missing_json += "]}";
    write_text_file(missing_path, missing_json);

    const auto manifest_json =
        std::string("{\"schema_version\":\"anchorworks_native_directory_intake_manifest@1\"") +
        ",\"ok\":true" +
        ",\"input_dir\":\"" + json_escape(input_dir.string()) + "\"" +
        ",\"authority\":\"" + json_escape(authority_path.string()) + "\"" +
        ",\"output\":\"" + json_escape(output.string()) + "\"" +
        ",\"source_id\":\"" + json_escape(source_id_prefix) + "\"" +
        ",\"window_radius\":" + std::to_string(window_radius) +
        ",\"file_count\":" + std::to_string(files.size()) +
        ",\"skipped_file_count\":" + std::to_string(skipped.size()) +
        ",\"skipped_files\":" + json_skipped_files(skipped) +
        ",\"paragraph_count\":" + std::to_string(stats.paragraph_count) +
        ",\"anchor_observation_count\":" + std::to_string(stats.anchor_observation_count) +
        ",\"countable_anchor_observation_count\":" + std::to_string(stats.countable_anchor_observation_count) +
        ",\"missing_anchor_count\":" + std::to_string(missing.size()) +
        ",\"source_local_symbol_count\":" + std::to_string(source_local.size()) +
        ",\"record_count\":" + std::to_string(relations.size()) +
        ",\"relation_observation_count\":" + std::to_string(observation_count) +
        ",\"record_size\":24" +
        ",\"raw_text_in_count_spine\":false}";
    write_text_file(manifest, manifest_json);

    std::cout << "{\"ok\":true,\"command\":\"intake-dir\",\"file_count\":" << files.size()
              << ",\"skipped_file_count\":" << skipped.size()
              << ",\"record_count\":" << relations.size()
              << ",\"missing_anchor_count\":" << missing.size()
              << ",\"source_local_symbol_count\":" << source_local.size() << "}\n";
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

double offset_weight(std::int8_t offset) {
    const auto distance = std::abs(static_cast<int>(offset));
    if (distance <= 0) {
        return 0.0;
    }
    return 1.0 / static_cast<double>(distance);
}

struct CountCandidate {
    double score = 0.0;
    std::uint64_t observations = 0;
    std::set<awsc::Symbol> roots;
    std::map<int, std::uint64_t> offsets;
};

std::map<awsc::Symbol, CountCandidate> score_count_candidates(
    const std::filesystem::path& counts,
    const std::set<awsc::Symbol>& context_symbols,
    const std::set<std::uint8_t>& allowed_lanes
) {
    const auto records = awsc::read_awss_stream(counts);
    std::map<awsc::Symbol, CountCandidate> candidates;
    for (const auto& record : records) {
        if (context_symbols.count(record.root) == 0) {
            continue;
        }
        if (!allowed_lanes.empty() && allowed_lanes.count(record.lane) == 0) {
            continue;
        }
        const auto weight = offset_weight(record.offset);
        if (weight <= 0.0) {
            continue;
        }
        auto& candidate = candidates[record.neighbor];
        candidate.score += static_cast<double>(record.count) * weight;
        candidate.observations += record.count;
        candidate.roots.insert(record.root);
        candidate.offsets[static_cast<int>(record.offset)] += record.count;
    }
    return candidates;
}

struct ManifestBlock {
    std::uint64_t block_id = 0;
    std::string source_file;
    std::string doc_id;
    std::uint64_t block_line_start = 0;
    std::uint64_t block_line_end = 0;
    std::uint64_t document_line_start = 0;
    std::uint64_t document_line_end = 0;
    std::vector<std::string> anchors;
};

std::vector<ManifestBlock> read_manifest_blocks(const std::filesystem::path& manifest) {
    const auto text = read_text_file(manifest);
    std::vector<ManifestBlock> blocks;
    for (const auto& object : json_objects_containing_key(text, "block_id")) {
        ManifestBlock block;
        block.block_id = object_u64(object, "block_id");
        block.source_file = object_value(object, "source_file");
        block.doc_id = object_value(object, "doc_id");
        block.block_line_start = object_u64(object, "block_line_start");
        block.block_line_end = object_u64(object, "block_line_end");
        block.document_line_start = object_u64(object, "document_line_start");
        block.document_line_end = object_u64(object, "document_line_end");
        block.anchors = object_string_array(object, "anchors");
        if (!block.source_file.empty()) {
            blocks.push_back(block);
        }
    }
    return blocks;
}

struct NativeBlockIndex {
    std::map<std::uint64_t, ManifestBlock> blocks;
    std::map<std::string, std::vector<std::uint64_t>> postings;
    std::map<std::string, std::string> anchor_to_symbol_hex;
    std::map<std::string, std::string> symbol_hex_to_anchor;
};

NativeBlockIndex make_native_block_index(const std::vector<ManifestBlock>& blocks) {
    NativeBlockIndex index;
    for (const auto& block : blocks) {
        index.blocks[block.block_id] = block;
        std::set<std::string> unique_anchors(block.anchors.begin(), block.anchors.end());
        for (const auto& anchor : unique_anchors) {
            index.postings[anchor].push_back(block.block_id);
        }
    }
    return index;
}

void write_native_block_index(const std::filesystem::path& path, const NativeBlockIndex& index) {
    std::filesystem::create_directories(path.parent_path());
    const auto tmp = path.string() + ".tmp";
    {
        std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error("cannot open native block index for writing: " + tmp);
        }
        out.write("AWBI0001", 8);
        write_u64(out, static_cast<std::uint64_t>(index.blocks.size()));
        for (const auto& [block_id, block] : index.blocks) {
            write_u64(out, block_id);
            write_u64(out, block.block_line_start);
            write_u64(out, block.block_line_end);
            write_u64(out, block.document_line_start);
            write_u64(out, block.document_line_end);
            write_index_string(out, block.source_file);
            write_index_string(out, block.doc_id);
        }
        write_u64(out, static_cast<std::uint64_t>(index.postings.size()));
        for (const auto& [anchor, block_ids] : index.postings) {
            write_index_string(out, anchor);
            write_u64(out, static_cast<std::uint64_t>(block_ids.size()));
            for (const auto block_id : block_ids) {
                write_u64(out, block_id);
            }
        }
        write_u64(out, static_cast<std::uint64_t>(index.anchor_to_symbol_hex.size()));
        for (const auto& [anchor, symbol_hex] : index.anchor_to_symbol_hex) {
            write_index_string(out, anchor);
            write_index_string(out, symbol_hex);
        }
        if (!out) {
            throw std::runtime_error("failed writing native block index: " + tmp);
        }
    }
    std::filesystem::rename(tmp, path);
}

NativeBlockIndex read_native_block_index(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot open native block index for reading: " + path.string());
    }
    char magic[8] = {};
    in.read(magic, 8);
    if (std::string(magic, 8) != "AWBI0001") {
        throw std::runtime_error("invalid native block index magic: " + path.string());
    }
    NativeBlockIndex index;
    const auto block_count = read_u64(in);
    for (std::uint64_t i = 0; i < block_count; ++i) {
        ManifestBlock block;
        block.block_id = read_u64(in);
        block.block_line_start = read_u64(in);
        block.block_line_end = read_u64(in);
        block.document_line_start = read_u64(in);
        block.document_line_end = read_u64(in);
        block.source_file = read_index_string(in);
        block.doc_id = read_index_string(in);
        index.blocks[block.block_id] = block;
    }
    const auto posting_count = read_u64(in);
    for (std::uint64_t i = 0; i < posting_count; ++i) {
        const auto anchor = read_index_string(in);
        const auto block_id_count = read_u64(in);
        auto& block_ids = index.postings[anchor];
        block_ids.reserve(static_cast<std::size_t>(block_id_count));
        for (std::uint64_t j = 0; j < block_id_count; ++j) {
            block_ids.push_back(read_u64(in));
        }
    }
    if (in.peek() != std::char_traits<char>::eof()) {
        const auto authority_count = read_u64(in);
        for (std::uint64_t i = 0; i < authority_count; ++i) {
            const auto anchor = read_index_string(in);
            const auto symbol_hex = read_index_string(in);
            index.anchor_to_symbol_hex[anchor] = symbol_hex;
            index.symbol_hex_to_anchor[symbol_hex] = anchor;
        }
    }
    return index;
}

int run_build_aw_index(int argc, char** argv) {
    const auto manifest_path = std::filesystem::path(arg_value(argc, argv, "--manifest"));
    const auto output_path = std::filesystem::path(arg_value(argc, argv, "--output"));
    const auto authority_arg = optional_arg_value(argc, argv, "--authority", "");
    const auto blocks = read_manifest_blocks(manifest_path);
    auto index = make_native_block_index(blocks);
    if (!authority_arg.empty()) {
        const auto authority = read_authority_snapshot(std::filesystem::path(authority_arg));
        for (const auto& [anchor, entry] : authority) {
            const auto symbol_hex = awsc::symbol_to_hex(entry.symbol);
            index.anchor_to_symbol_hex[anchor] = symbol_hex;
            index.symbol_hex_to_anchor[symbol_hex] = anchor;
        }
    }
    write_native_block_index(output_path, index);
    std::cout << "{"
              << "\"ok\":true,"
              << "\"command\":\"build-aw-index\","
              << "\"manifest\":\"" << json_escape(manifest_path.string()) << "\","
              << "\"output\":\"" << json_escape(output_path.string()) << "\","
              << "\"block_count\":" << index.blocks.size() << ","
              << "\"posting_anchor_count\":" << index.postings.size() << ","
              << "\"authority_anchor_count\":" << index.anchor_to_symbol_hex.size()
              << "}\n";
    return 0;
}

std::vector<std::string> unique_ordered_anchors(const std::vector<std::string>& anchors) {
    std::vector<std::string> out;
    std::set<std::string> seen;
    for (const auto& anchor : anchors) {
        if (seen.insert(anchor).second) {
            out.push_back(anchor);
        }
    }
    return out;
}

std::string json_string_array(const std::vector<std::string>& values) {
    std::string out = "[";
    bool first = true;
    for (const auto& value : values) {
        if (!first) {
            out += ",";
        }
        first = false;
        out += "\"" + json_escape(value) + "\"";
    }
    out += "]";
    return out;
}

int run_search_aw(int argc, char** argv) {
    const auto query = arg_value(argc, argv, "--query");
    const auto authority_arg = optional_arg_value(argc, argv, "--authority", "");
    const auto counts_path = std::filesystem::path(arg_value(argc, argv, "--counts"));
    const auto manifest_arg = optional_arg_value(argc, argv, "--manifest", "");
    const auto block_index_arg = optional_arg_value(argc, argv, "--block-index", "");
    const auto rag_copy = arg_value(argc, argv, "--rag-copy");
    const auto top_k = static_cast<std::size_t>(arg_u64(argc, argv, "--top-k", 10));
    if (manifest_arg.empty() && block_index_arg.empty()) {
        throw std::runtime_error("search-aw requires --manifest or --block-index");
    }

    NativeBlockIndex block_index;
    const bool using_block_index = !block_index_arg.empty();
    if (using_block_index) {
        block_index = read_native_block_index(std::filesystem::path(block_index_arg));
    }

    std::map<std::string, AuthorityEntry> authority;
    if (!authority_arg.empty()) {
        authority = read_authority_snapshot(std::filesystem::path(authority_arg));
    } else if (!using_block_index || block_index.anchor_to_symbol_hex.empty()) {
        throw std::runtime_error("search-aw requires --authority unless --block-index contains authority mappings");
    }

    std::map<awsc::Symbol, std::string> anchor_by_symbol;
    if (!authority.empty()) {
        for (const auto& [anchor, entry] : authority) {
            anchor_by_symbol[entry.symbol] = anchor;
        }
    } else {
        for (const auto& [symbol_hex, anchor] : block_index.symbol_hex_to_anchor) {
            anchor_by_symbol[awsc::symbol_from_hex(symbol_hex)] = anchor;
        }
    }

    std::vector<std::string> query_anchors = unique_ordered_anchors(extract_anchors_native(query));
    std::set<awsc::Symbol> context_symbols;
    std::vector<std::string> represented_anchors;
    std::vector<std::string> missing_anchors;
    for (const auto& anchor : query_anchors) {
        if (!authority.empty()) {
            const auto found = authority.find(anchor);
            if (found == authority.end()) {
                missing_anchors.push_back(anchor);
                continue;
            }
            represented_anchors.push_back(anchor);
            context_symbols.insert(found->second.symbol);
        } else {
            const auto found = block_index.anchor_to_symbol_hex.find(anchor);
            if (found == block_index.anchor_to_symbol_hex.end()) {
                missing_anchors.push_back(anchor);
                continue;
            }
            represented_anchors.push_back(anchor);
            context_symbols.insert(awsc::symbol_from_hex(found->second));
        }
    }

    const std::set<std::uint8_t> allowed_lanes = {
        awsc::LANE_CANONICAL,
        awsc::LANE_MATH_COMPANION,
        awsc::LANE_STRUCTURAL_COMPANION,
        awsc::LANE_SOURCE_SPECIFIC,
        awsc::LANE_USER_LEXICON,
    };
    const auto candidates = score_count_candidates(counts_path, context_symbols, allowed_lanes);
    std::set<std::string> candidate_anchors;
    for (const auto& [symbol, candidate] : candidates) {
        const auto found = anchor_by_symbol.find(symbol);
        if (found != anchor_by_symbol.end()) {
            candidate_anchors.insert(found->second);
        }
    }

    std::map<std::string, double> query_anchor_weights;
    for (const auto& anchor : represented_anchors) {
        if (is_blocked_focus_anchor(anchor)) {
            continue;
        }
        for (const auto& variant : attention_variants_for_anchor(anchor)) {
            const auto weight = anchor_specificity_weight(anchor);
            const auto existing = query_anchor_weights.find(variant);
            if (existing == query_anchor_weights.end() || existing->second < weight) {
                query_anchor_weights[variant] = weight;
            }
        }
    }

    struct Hit {
        ManifestBlock block;
        std::vector<std::string> query_hits;
        std::vector<std::string> candidate_hits;
        double score = 0.0;
    };

    std::vector<Hit> hits;
    const auto search_surface = using_block_index ? "native_block_index" : "manifest_scan";
    if (using_block_index) {
        std::map<std::string, std::uint64_t> block_frequency;
        for (const auto& [anchor, block_ids] : block_index.postings) {
            block_frequency[anchor] = static_cast<std::uint64_t>(block_ids.size());
        }
        std::map<std::uint64_t, Hit> hit_by_block;
        auto add_anchor_hits = [&](const std::string& anchor, bool query_anchor, double base_weight) {
            const auto posting = block_index.postings.find(anchor);
            if (posting == block_index.postings.end()) {
                return;
            }
            const auto rarity = anchor_rarity_weight(anchor, block_frequency, block_index.blocks.size());
            for (const auto block_id : posting->second) {
                const auto block = block_index.blocks.find(block_id);
                if (block == block_index.blocks.end()) {
                    continue;
                }
                auto& hit = hit_by_block[block_id];
                hit.block = block->second;
                if (query_anchor) {
                    if (std::find(hit.query_hits.begin(), hit.query_hits.end(), anchor) == hit.query_hits.end()) {
                        hit.query_hits.push_back(anchor);
                        hit.score += base_weight * rarity * 1000.0;
                    }
                } else {
                    if (std::find(hit.candidate_hits.begin(), hit.candidate_hits.end(), anchor) == hit.candidate_hits.end()) {
                        hit.candidate_hits.push_back(anchor);
                        hit.score += 0.05 * base_weight * rarity;
                    }
                }
            }
        };
        for (const auto& [anchor, base_weight] : query_anchor_weights) {
            add_anchor_hits(anchor, true, base_weight);
        }
        for (const auto& anchor : candidate_anchors) {
            if (is_blocked_focus_anchor(anchor)) {
                continue;
            }
            add_anchor_hits(anchor, false, anchor_specificity_weight(anchor));
        }
        for (auto& [block_id, hit] : hit_by_block) {
            if (hit.score > 0.0) {
                hits.push_back(hit);
            }
        }
    } else {
    const auto manifest_blocks = read_manifest_blocks(std::filesystem::path(manifest_arg));
    std::map<std::string, std::uint64_t> block_frequency;
    for (const auto& block : manifest_blocks) {
        std::set<std::string> unique_block_anchors(block.anchors.begin(), block.anchors.end());
        for (const auto& anchor : unique_block_anchors) {
            block_frequency[anchor] += 1;
        }
    }

    for (const auto& block : manifest_blocks) {
        Hit hit;
        hit.block = block;
        std::set<std::string> block_anchors(block.anchors.begin(), block.anchors.end());
        double query_score = 0.0;
        double candidate_score = 0.0;
        for (const auto& [anchor, base_weight] : query_anchor_weights) {
            if (block_anchors.count(anchor) > 0) {
                hit.query_hits.push_back(anchor);
                query_score += base_weight * anchor_rarity_weight(anchor, block_frequency, manifest_blocks.size());
            }
        }
        for (const auto& anchor : candidate_anchors) {
            if (is_blocked_focus_anchor(anchor)) {
                continue;
            }
            if (block_anchors.count(anchor) > 0) {
                hit.candidate_hits.push_back(anchor);
                candidate_score += 0.05 * anchor_specificity_weight(anchor) *
                                   anchor_rarity_weight(anchor, block_frequency, manifest_blocks.size());
            }
        }
        hit.score = query_score * 1000.0 + candidate_score;
        if (hit.score > 0.0) {
            hits.push_back(hit);
        }
    }
    }
    std::sort(hits.begin(), hits.end(), [](const auto& left, const auto& right) {
        if (left.score != right.score) return left.score > right.score;
        if (left.query_hits.size() != right.query_hits.size()) return left.query_hits.size() > right.query_hits.size();
        return left.block.block_id < right.block.block_id;
    });
    if (hits.size() > top_k) {
        hits.resize(top_k);
    }

    std::cout << "{"
              << "\"ok\":true,"
              << "\"command\":\"search-aw\","
              << "\"search_surface\":\"" << search_surface << "\","
              << "\"query\":\"" << json_escape(query) << "\","
              << "\"query_anchors\":" << json_string_array(query_anchors) << ","
              << "\"represented_anchors\":" << json_string_array(represented_anchors) << ","
              << "\"missing_anchors\":" << json_string_array(missing_anchors) << ","
              << "\"represented_anchor_count\":" << represented_anchors.size() << ","
              << "\"count_candidate_count\":" << candidates.size() << ","
              << "\"hits\":[";
    bool first = true;
    for (const auto& hit : hits) {
        if (!first) {
            std::cout << ",";
        }
        first = false;
        std::cout << "{"
                  << "\"doc_id\":\"" << json_escape(hit.block.doc_id) << "\","
                  << "\"source_file\":\"" << json_escape(hit.block.source_file) << "\","
                  << "\"block_id\":" << hit.block.block_id << ","
                  << "\"block_line_start\":" << hit.block.block_line_start << ","
                  << "\"block_line_end\":" << hit.block.block_line_end << ","
                  << "\"document_line_start\":" << hit.block.document_line_start << ","
                  << "\"document_line_end\":" << hit.block.document_line_end << ","
                  << "\"rag_copy\":\"" << json_escape(rag_copy) << "\","
                  << "\"score\":" << hit.score << ","
                  << "\"query_anchor_hits\":" << json_string_array(hit.query_hits) << ","
                  << "\"count_candidate_anchor_hits\":" << json_string_array(hit.candidate_hits)
                  << "}";
    }
    std::cout << "]}\n";
    return 0;
}

void print_usage() {
    std::cerr
        << "anchorworks-symbol-counts commands:\n"
        << "  intake-text --input <prepared.txt> --authority <snapshot.json> --output <counts.bin> --manifest <manifest.json> --missing <missing.json> [--window-radius <n>]\n"
        << "  intake-dir --input-dir <dir> --authority <snapshot.json> --output <counts.bin> --manifest <manifest.json> --missing <missing.json> [--window-radius <n>]\n"
        << "  build-aw-index --manifest <manifest.json> --output <blocks.awbi>\n"
        << "  search-aw --query <text> --authority <snapshot.json> --counts <awss.bin> (--manifest <manifest.json> | --block-index <blocks.awbi>) --rag-copy <file.aw.md> [--top-k <n>]\n"
        << "  score-stream --input <awss.bin> --context <hex,hex> [--top-k <n>] [--allowed-lanes <ids>]\n";
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
        if (command == "intake-dir") {
            return run_intake_dir(argc, argv);
        }
        if (command == "build-aw-index") {
            return run_build_aw_index(argc, argv);
        }
        if (command == "search-aw") {
            return run_search_aw(argc, argv);
        }
        if (command == "score-stream") {
            const auto input = std::filesystem::path(arg_value(argc, argv, "--input"));
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

            std::set<awsc::Symbol> context_symbols;
            for (const auto& item : context_items) {
                context_symbols.insert(awsc::symbol_from_hex(item));
            }
            const auto records = awsc::read_awss_stream(input);
            std::map<awsc::Symbol, CountCandidate> candidates;
            std::set<awsc::Symbol> loaded_context;
            for (const auto& record : records) {
                if (context_symbols.count(record.root) == 0) {
                    continue;
                }
                loaded_context.insert(record.root);
                if (!allowed_lanes.empty() && allowed_lanes.count(record.lane) == 0) {
                    continue;
                }
                const auto weight = offset_weight(record.offset);
                if (weight <= 0.0) {
                    continue;
                }
                auto& candidate = candidates[record.neighbor];
                candidate.score += static_cast<double>(record.count) * weight;
                candidate.observations += record.count;
                candidate.roots.insert(record.root);
                candidate.offsets[static_cast<int>(record.offset)] += record.count;
            }

            std::vector<std::pair<awsc::Symbol, CountCandidate>> ranked(candidates.begin(), candidates.end());
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
                      << "\"command\":\"score-stream\","
                      << "\"context_count\":" << loaded_context.size() << ","
                      << "\"record_count\":" << records.size() << ","
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
                          << ",\"offsets\":[";
                bool first_offset = true;
                for (const auto& [offset, observations] : candidate.offsets) {
                    if (!first_offset) {
                        std::cout << ",";
                    }
                    first_offset = false;
                    std::cout << "{\"offset\":" << offset << ",\"observations\":" << observations << "}";
                }
                std::cout << "]}";
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
