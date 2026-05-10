# Binary Serialization Research - Key Findings

## Source: jstrong.dev - Binary Serialization Best Practices

### Core Principles

**1. Make it easy for the computer**
- Binary representations store data similarly or identically to the way it will be represented in memory
- Entire categories of parsing work are avoided
- If types are known, the exact size needed to store the data can be known
- Far more compact than plain-text formats

**2. Fixed-length records enable predictable performance**
- All records have the same size
- File size / record size = number of records
- Can memory-map the entire file and treat it as a big byte slice
- Enables cache-line optimization (64-byte cache lines)

**3. Document the format explicitly**
- Use ASCII diagrams to show byte layout
- Define constants for field offsets
- Make serialization code self-documenting

**4. Alignment matters**
- Use `#[repr(align(N))]` to ensure cache-line alignment
- Powers of two are good for performance
- 32-byte records fit 2 per 64-byte cache line

**5. Avoid branching in hot loops**
- Use arithmetic masks instead of if/else
- Convert booleans to f64 (0.0 or 1.0) and multiply
- CPUs prefer doing the same work repeatedly over branching

### Example: 32-Byte Trade Record

```
                     1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|e|b|q|s| srvtm | time: u64     | price: f64    | amount: f64   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

e = exch (u8)
b = base currency (u8)
q = quote currency (u8)
s = side (u8) - 0=None, 1=Bid, 2=Ask
srvtm = server_time (i32) - 0=None, other=nano offset from time
time = timestamp (u64)
price = price (f64)
amount = amount (f64)
```

### Deserialization Pattern

```rust
impl<'a> PackedTradeData<'a> {
    const EXCH_OFFSET: usize = 0;
    const BASE_OFFSET: usize = 1;
    const QUOTE_OFFSET: usize = 2;
    const SIDE_OFFSET: usize = 3;
    const SERVER_TIME_OFFSET: usize = 4;
    const TIME_OFFSET: usize = 8;
    const PRICE_OFFSET: usize = 16;
    const AMOUNT_OFFSET: usize = 24;

    #[inline]
    pub fn time(&self) -> u64 {
        u64::from_le_bytes(
            (&self.0[Self::TIME_OFFSET..(Self::TIME_OFFSET + 8)])
                .try_into()
                .unwrap()
        )
    }

    #[inline]
    pub fn price(&self) -> f64 {
        f64::from_le_bytes(
            (&self.0[Self::PRICE_OFFSET..(Self::PRICE_OFFSET + 8)])
                .try_into()
                .unwrap()
        )
    }
}
```

### Serialization Pattern

```rust
pub fn serialize<'a, 'b>(buf: &'a mut [u8], trade: &'b CsvTrade) {
    assert_eq!(buf.len(), SERIALIZED_SIZE);

    buf[EXCH_OFFSET] = u8::from(trade.exch);
    buf[BASE_OFFSET] = u8::from(trade.ticker.base);
    buf[QUOTE_OFFSET] = u8::from(trade.ticker.quote);

    match trade.side {
        Some(side) => {
            buf[SIDE_OFFSET] = u8::from(side);
        }
        None => {
            buf[SIDE_OFFSET] = 0;
        }
    }

    (&mut buf[TIME_OFFSET..(TIME_OFFSET + 8)])
        .copy_from_slice(&trade.time.to_le_bytes()[..]);
    (&mut buf[PRICE_OFFSET..(PRICE_OFFSET + 8)])
        .copy_from_slice(&trade.price.to_le_bytes()[..]);
    (&mut buf[AMOUNT_OFFSET..(AMOUNT_OFFSET + 8)])
        .copy_from_slice(&trade.amount.to_le_bytes()[..]);
}
```

### Performance Results

- **CSV parsing:** 1.9 million rows/sec
- **Binary (cold cache):** 16.1 million rows/sec (8.5x faster)
- **Binary (warm cache):** 117.6 million rows/sec (62x faster)
- **Binary (z1d.metal warm):** 173 million rows/sec (91x faster)

### Key Takeaways for Node 5

1. **Use fixed-length records** - Predictable, fast, memory-mappable
2. **Document byte layout with ASCII diagrams** - Makes format explicit
3. **Define field offsets as constants** - Self-documenting code
4. **Use Little Endian** - Standard for x86/x64
5. **Align to cache lines** - 32 or 64 bytes
6. **Avoid Optional wrapper overhead** - Use sentinel values (0 for None)
7. **Make serialize/deserialize mirror each other** - Same field offsets, same byte order
8. **Use `copy_from_slice` for multi-byte fields** - Safe, explicit
9. **Use `from_le_bytes` for deserialization** - Explicit endianness
10. **Test with exact byte buffers** - Verify serialization round-trips correctly


---

## SQLite WAL Mode - Key Findings

### How WAL Works

**Traditional rollback journal:**
- Writes copy of original content to rollback journal
- Writes changes directly to database file
- On crash: replay rollback journal to revert changes
- COMMIT = delete rollback journal

**Write-Ahead Log (WAL):**
- Original content preserved in database file
- Changes appended to separate WAL file
- COMMIT = append special commit record to WAL
- Multiple transactions can be appended to single WAL file

**Three primitive operations:**
1. Reading
2. Writing
3. Checkpointing (moving WAL transactions back to main database)

### Checkpointing

- Automatic checkpoint when WAL reaches 1000 pages (default)
- Transfers WAL file transactions back to original database
- Can run concurrently with readers
- Must stop when reaching a page past any current reader's end mark
- Long-running read transactions can prevent checkpoint progress

### Crash Recovery

- WAL file contains commit records
- On crash: replay WAL file from beginning to end
- Checksums verified on each frame
- Database restored to last valid commit

### Performance Characteristics

**Advantages:**
- Significantly faster in most scenarios
- Readers don't block writers, writers don't block readers
- More sequential disk I/O
- Fewer fsync() operations

**Disadvantages:**
- All processes must be on same host (requires shared memory)
- Not atomic across multiple ATTACHed databases
- Additional -wal and -shm files
- Checkpointing overhead

### Key Takeaways for Node 5

1. **WAL is proven for crash safety** - Used by SQLite since 2010
2. **Append-only writes are fast** - Sequential I/O
3. **Checkpointing is essential** - Must transfer WAL to main storage periodically
4. **Shared memory enables concurrency** - wal-index in shared memory for fast lookups
5. **Commit records mark transaction boundaries** - Special record type in WAL
6. **Checksums prevent corruption** - Every frame verified on replay
