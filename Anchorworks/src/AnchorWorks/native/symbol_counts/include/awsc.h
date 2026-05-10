#pragma once

#include <array>
#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace anchorworks::awsc {

using Symbol = std::array<std::uint8_t, 5>;

constexpr std::uint16_t VERSION = 0x0101;
constexpr std::uint16_t HEADER_SIZE = 64;
constexpr std::uint16_t ROW_SIZE = 16;

constexpr std::uint8_t LANE_CANONICAL = 0;
constexpr std::uint8_t LANE_MATH_COMPANION = 1;
constexpr std::uint8_t LANE_STRUCTURAL_COMPANION = 2;
constexpr std::uint8_t LANE_SOURCE_SPECIFIC = 3;
constexpr std::uint8_t LANE_SOURCE_LOCAL_TEMP = 4;
constexpr std::uint8_t LANE_USER_LEXICON = 5;
constexpr std::uint8_t LANE_RESERVED_ERROR = 255;

struct Relation {
    Symbol neighbor{};
    std::int8_t offset = 0;
    std::uint8_t lane = LANE_CANONICAL;
    std::uint8_t flags = 0;
    std::uint64_t count = 0;
};

struct Cell {
    Symbol root{};
    std::uint8_t root_lane = LANE_CANONICAL;
    std::uint16_t flags = 0;
    std::uint64_t generation = 0;
    std::uint64_t wal_frame = 0;
    std::uint64_t overflow_offset = 0;
    std::vector<Relation> relations;
};

struct StreamRecord {
    Symbol root{};
    Symbol neighbor{};
    std::int8_t offset = 0;
    std::uint8_t lane = LANE_CANONICAL;
    std::uint8_t flags = 0;
    std::uint8_t root_lane = LANE_CANONICAL;
    std::uint64_t count = 0;
};

struct VerifyResult {
    std::uint64_t checked = 0;
    std::vector<std::string> errors;
};

bool is_valid_relation_lane(std::uint8_t lane);
std::string symbol_to_hex(const Symbol& symbol);
Symbol symbol_from_hex(const std::string& text);

std::vector<StreamRecord> read_awss_stream(const std::filesystem::path& path);
void merge_stream_to_cells(
    const std::filesystem::path& input_path,
    const std::filesystem::path& output_root,
    std::uint64_t generation
);

void write_cell(const std::filesystem::path& path, const Cell& cell);
Cell read_cell(const std::filesystem::path& path);
VerifyResult verify_root(const std::filesystem::path& root);

}  // namespace anchorworks::awsc
