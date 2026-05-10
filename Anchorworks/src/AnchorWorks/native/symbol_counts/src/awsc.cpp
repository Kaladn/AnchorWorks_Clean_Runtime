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

std::uint16_t read_u16_le(const std::vector<std::uint8_t>& data, std::size_t offset) {
    return static_cast<std::uint16_t>(data[offset]) |
           (static_cast<std::uint16_t>(data[offset + 1]) << 8);
}

std::uint32_t read_u32_le(const std::vector<std::uint8_t>& data, std::size_t offset) {
    return static_cast<std::uint32_t>(data[offset]) |
           (static_cast<std::uint32_t>(data[offset + 1]) << 8) |
           (static_cast<std::uint32_t>(data[offset + 2]) << 16) |
           (static_cast<std::uint32_t>(data[offset + 3]) << 24);
}

std::uint64_t read_u64_le(const std::vector<std::uint8_t>& data, std::size_t offset) {
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < 8; ++i) {
        value |= static_cast<std::uint64_t>(data[offset + i]) << (8 * i);
    }
    return value;
}

void append_u16_le(std::vector<std::uint8_t>& data, std::uint16_t value) {
    data.push_back(static_cast<std::uint8_t>(value & 0xff));
    data.push_back(static_cast<std::uint8_t>((value >> 8) & 0xff));
}

void append_u32_le(std::vector<std::uint8_t>& data, std::uint32_t value) {
    for (int i = 0; i < 4; ++i) {
        data.push_back(static_cast<std::uint8_t>((value >> (8 * i)) & 0xff));
    }
}

void append_u64_le(std::vector<std::uint8_t>& data, std::uint64_t value) {
    for (int i = 0; i < 8; ++i) {
        data.push_back(static_cast<std::uint8_t>((value >> (8 * i)) & 0xff));
    }
}

std::vector<std::uint8_t> read_all(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot open file for reading: " + path.string());
    }
    return std::vector<std::uint8_t>(
        std::istreambuf_iterator<char>(in),
        std::istreambuf_iterator<char>()
    );
}

void write_all_atomic(const std::filesystem::path& path, const std::vector<std::uint8_t>& data) {
    std::filesystem::create_directories(path.parent_path());
    const auto tmp = path.string() + ".tmp";
    {
        std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error("cannot open temp file for writing: " + tmp);
        }
        out.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
        if (!out) {
            throw std::runtime_error("failed writing temp file: " + tmp);
        }
    }
    std::filesystem::rename(tmp, path);
}

std::uint32_t crc32_bytes(const std::vector<std::uint8_t>& data) {
    static std::array<std::uint32_t, 256> table{};
    static bool initialized = false;
    if (!initialized) {
        for (std::uint32_t i = 0; i < 256; ++i) {
            std::uint32_t c = i;
            for (int j = 0; j < 8; ++j) {
                c = (c & 1U) ? (0xEDB88320U ^ (c >> 1U)) : (c >> 1U);
            }
            table[i] = c;
        }
        initialized = true;
    }
    std::uint32_t c = 0xFFFFFFFFU;
    for (std::uint8_t byte : data) {
        c = table[(c ^ byte) & 0xFFU] ^ (c >> 8U);
    }
    return c ^ 0xFFFFFFFFU;
}

std::vector<Relation> merge_relations(const std::vector<Relation>& relations) {
    struct Key {
        std::int8_t offset = 0;
        Symbol neighbor{};
        std::uint8_t lane = 0;
        std::uint8_t flags = 0;

        bool operator<(const Key& other) const {
            if (offset != other.offset) return offset < other.offset;
            if (neighbor != other.neighbor) return neighbor < other.neighbor;
            if (lane != other.lane) return lane < other.lane;
            return flags < other.flags;
        }
    };

    std::map<Key, std::uint64_t> counts;
    for (const auto& relation : relations) {
        if (!is_valid_relation_lane(relation.lane)) {
            throw std::runtime_error("invalid relation lane");
        }
        if (relation.count == 0) {
            continue;
        }
        counts[Key{relation.offset, relation.neighbor, relation.lane, relation.flags}] += relation.count;
    }

    std::vector<Relation> out;
    out.reserve(counts.size());
    for (const auto& [key, count] : counts) {
        out.push_back(Relation{key.neighbor, key.offset, key.lane, key.flags, count});
    }
    std::sort(out.begin(), out.end(), [](const Relation& a, const Relation& b) {
        if (a.offset != b.offset) return a.offset < b.offset;
        if (a.count != b.count) return a.count > b.count;
        if (a.neighbor != b.neighbor) return a.neighbor < b.neighbor;
        return a.lane < b.lane;
    });
    return out;
}

std::filesystem::path cell_path_for(const std::filesystem::path& root, const Symbol& symbol) {
    const auto hex = symbol_to_hex(symbol);
    return root / "cells" / hex.substr(0, 2) / (hex + ".cell");
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
    for (char ch : text) {
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
        throw std::runtime_error("AWSS stream size is not divisible by 24 bytes");
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
            throw std::runtime_error("AWSS stream contains invalid lane");
        }
        records.push_back(record);
    }
    return records;
}

void write_cell(const std::filesystem::path& path, const Cell& cell) {
    if (!is_valid_relation_lane(cell.root_lane)) {
        throw std::runtime_error("invalid root lane");
    }
    const auto relations = merge_relations(cell.relations);
    std::vector<std::uint8_t> payload;
    payload.reserve(relations.size() * ROW_SIZE);
    for (const auto& relation : relations) {
        payload.insert(payload.end(), relation.neighbor.begin(), relation.neighbor.end());
        payload.push_back(static_cast<std::uint8_t>(relation.offset));
        payload.push_back(relation.lane);
        payload.push_back(relation.flags);
        append_u64_le(payload, relation.count);
    }

    std::vector<std::uint8_t> data;
    data.reserve(HEADER_SIZE + payload.size());
    data.insert(data.end(), {'A', 'W', 'S', 'C'});
    append_u16_le(data, VERSION);
    append_u16_le(data, HEADER_SIZE);
    append_u64_le(data, HEADER_SIZE + payload.size());
    append_u64_le(data, cell.generation);
    append_u64_le(data, cell.wal_frame);
    data.insert(data.end(), cell.root.begin(), cell.root.end());
    data.push_back(cell.root_lane);
    append_u16_le(data, cell.flags);
    append_u32_le(data, static_cast<std::uint32_t>(relations.size()));
    append_u16_le(data, ROW_SIZE);
    append_u16_le(data, 0);
    append_u32_le(data, static_cast<std::uint32_t>(payload.size()));
    append_u32_le(data, crc32_bytes(payload));
    append_u64_le(data, cell.overflow_offset);
    if (data.size() != HEADER_SIZE) {
        throw std::runtime_error("internal AWSC header size error");
    }
    data.insert(data.end(), payload.begin(), payload.end());
    write_all_atomic(path, data);
}

Cell read_cell(const std::filesystem::path& path) {
    const auto data = read_all(path);
    if (data.size() < HEADER_SIZE) {
        throw std::runtime_error("AWSC cell shorter than header");
    }
    if (!(data[0] == 'A' && data[1] == 'W' && data[2] == 'S' && data[3] == 'C')) {
        throw std::runtime_error("invalid AWSC magic");
    }
    const auto version = read_u16_le(data, 4);
    const auto header_size = read_u16_le(data, 6);
    if (version != VERSION || header_size != HEADER_SIZE) {
        throw std::runtime_error("unsupported AWSC version or header size");
    }
    const auto total_size = read_u64_le(data, 8);
    if (total_size != data.size()) {
        throw std::runtime_error("AWSC total size mismatch");
    }
    Cell cell{};
    cell.generation = read_u64_le(data, 16);
    cell.wal_frame = read_u64_le(data, 24);
    std::copy_n(data.begin() + 32, 5, cell.root.begin());
    cell.root_lane = data[37];
    cell.flags = read_u16_le(data, 38);
    const auto row_count = read_u32_le(data, 40);
    const auto row_size = read_u16_le(data, 44);
    const auto payload_size = read_u32_le(data, 48);
    const auto checksum = read_u32_le(data, 52);
    cell.overflow_offset = read_u64_le(data, 56);
    if (!is_valid_relation_lane(cell.root_lane)) {
        throw std::runtime_error("invalid AWSC root lane");
    }
    if (row_size != ROW_SIZE || payload_size != row_count * ROW_SIZE) {
        throw std::runtime_error("AWSC row size mismatch");
    }
    if (HEADER_SIZE + payload_size != data.size()) {
        throw std::runtime_error("AWSC payload size mismatch");
    }
    std::vector<std::uint8_t> payload(data.begin() + HEADER_SIZE, data.end());
    if (crc32_bytes(payload) != checksum) {
        throw std::runtime_error("AWSC CRC mismatch");
    }
    cell.relations.reserve(row_count);
    for (std::size_t offset = HEADER_SIZE; offset < data.size(); offset += ROW_SIZE) {
        Relation relation{};
        std::copy_n(data.begin() + static_cast<std::ptrdiff_t>(offset), 5, relation.neighbor.begin());
        relation.offset = static_cast<std::int8_t>(data[offset + 5]);
        relation.lane = data[offset + 6];
        relation.flags = data[offset + 7];
        relation.count = read_u64_le(data, offset + 8);
        if (!is_valid_relation_lane(relation.lane)) {
            throw std::runtime_error("invalid AWSC relation lane");
        }
        cell.relations.push_back(relation);
    }
    return cell;
}

void merge_stream_to_cells(
    const std::filesystem::path& input_path,
    const std::filesystem::path& output_root,
    std::uint64_t generation
) {
    struct RootBucket {
        std::uint8_t root_lane = LANE_CANONICAL;
        std::vector<Relation> relations;
    };

    std::map<Symbol, RootBucket> buckets;
    for (const auto& record : read_awss_stream(input_path)) {
        auto& bucket = buckets[record.root];
        if (bucket.relations.empty()) {
            bucket.root_lane = record.root_lane;
        } else if (bucket.root_lane != record.root_lane) {
            throw std::runtime_error("AWSS stream changes root lane for one symbol");
        }
        bucket.relations.push_back(Relation{
            record.neighbor,
            record.offset,
            record.lane,
            record.flags,
            record.count
        });
    }

    std::filesystem::create_directories(output_root / "indexes");
    for (const auto& [root, bucket] : buckets) {
        write_cell(cell_path_for(output_root, root), Cell{
            root,
            bucket.root_lane,
            0,
            generation,
            0,
            0,
            bucket.relations
        });
    }
    std::ofstream metadata(output_root / "metadata.json", std::ios::trunc);
    metadata << "{\n"
             << "  \"schema_version\": \"anchorworks_symbol_counts_binary@1.1\",\n"
             << "  \"cell_count\": " << buckets.size() << ",\n"
             << "  \"generation\": " << generation << "\n"
             << "}\n";
}

VerifyResult verify_root(const std::filesystem::path& root) {
    VerifyResult result{};
    const auto cells_root = root / "cells";
    if (!std::filesystem::exists(cells_root)) {
        result.errors.push_back("missing cells directory: " + cells_root.string());
        return result;
    }
    for (const auto& entry : std::filesystem::recursive_directory_iterator(cells_root)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".cell") {
            continue;
        }
        try {
            (void)read_cell(entry.path());
            ++result.checked;
        } catch (const std::exception& exc) {
            result.errors.push_back(entry.path().string() + ": " + exc.what());
        }
    }
    return result;
}

}  // namespace anchorworks::awsc
