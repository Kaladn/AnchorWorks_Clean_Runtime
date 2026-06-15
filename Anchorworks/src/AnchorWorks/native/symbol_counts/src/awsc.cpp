#include "awsc.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace anchorworks::awsc {
namespace {

constexpr std::size_t AWSS_RECORD_SIZE = 24;

std::uint64_t read_u64_le(const std::vector<std::uint8_t>& data, std::size_t offset) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < 8; ++i) {
        value |= static_cast<std::uint64_t>(data[offset + i]) << (8 * i);
    }
    return value;
}

std::vector<std::uint8_t> read_all(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot open count bin for reading: " + path.string());
    }
    return std::vector<std::uint8_t>(
        std::istreambuf_iterator<char>(in),
        std::istreambuf_iterator<char>()
    );
}

}  // namespace

bool is_valid_relation_lane(std::uint8_t lane) {
    return lane == LANE_CANONICAL ||
           lane == LANE_MATH_COMPANION ||
           lane == LANE_STRUCTURAL_COMPANION ||
           lane == LANE_SOURCE_SPECIFIC ||
           lane == LANE_SOURCE_LOCAL_TEMP ||
           lane == LANE_USER_LEXICON ||
           lane == LANE_RESERVED_ERROR;
}

std::string symbol_to_hex(const Symbol& symbol) {
    std::ostringstream out;
    out << std::uppercase << std::hex << std::setfill('0');
    for (auto byte : symbol) {
        out << std::setw(2) << static_cast<int>(byte);
    }
    return out.str();
}

Symbol symbol_from_hex(const std::string& text) {
    std::string value;
    std::size_t start = 0;
    if (text.size() >= 2 && text[0] == '0' && (text[1] == 'x' || text[1] == 'X')) {
        start = 2;
    }
    for (std::size_t index = start; index < text.size(); ++index) {
        const char ch = text[index];
        if (std::isxdigit(static_cast<unsigned char>(ch))) {
            value.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(ch))));
        }
    }
    if (value.size() != 10) {
        throw std::runtime_error("symbol hex must be exactly 10 hex characters");
    }
    Symbol symbol{};
    for (std::size_t i = 0; i < symbol.size(); ++i) {
        symbol[i] = static_cast<std::uint8_t>(std::stoul(value.substr(i * 2, 2), nullptr, 16));
    }
    return symbol;
}

std::vector<StreamRecord> read_awss_stream(const std::filesystem::path& path) {
    const auto data = read_all(path);
    if (data.size() % AWSS_RECORD_SIZE != 0) {
        throw std::runtime_error("count bin size is not divisible by 24 bytes");
    }
    std::vector<StreamRecord> records;
    records.reserve(data.size() / AWSS_RECORD_SIZE);
    for (std::size_t offset = 0; offset < data.size(); offset += AWSS_RECORD_SIZE) {
        StreamRecord record{};
        std::copy_n(data.begin() + static_cast<std::ptrdiff_t>(offset), 5, record.root.begin());
        std::copy_n(data.begin() + static_cast<std::ptrdiff_t>(offset + 5), 5, record.neighbor.begin());
        record.offset = static_cast<std::int8_t>(data[offset + 10]);
        record.lane = data[offset + 11];
        record.flags = data[offset + 12];
        record.root_lane = data[offset + 13];
        record.count = read_u64_le(data, offset + 16);
        if (!is_valid_relation_lane(record.lane) || !is_valid_relation_lane(record.root_lane)) {
            throw std::runtime_error("count bin contains invalid lane");
        }
        records.push_back(record);
    }
    return records;
}

}  // namespace anchorworks::awsc
