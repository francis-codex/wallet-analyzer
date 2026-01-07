# Solana Wallet Token Analyzer

Analyzes Solana wallet addresses to identify token creation patterns and categorize wallets based on trading volume.

## Quick Start

### Requirements
- Python 3.8 or higher
- Internet connection

### Installation

1. Install Python from https://python.org if not already installed

2. Install required library:
```bash
pip install requests
```

3. Create your input file `wallets.txt` with one wallet address per line:
```
7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM
... add more wallet addresses ...
```

4. Run the script:
```bash
python main.py
```

## How It Works

For each wallet address:
1. Fetches all tokens created by that wallet (via Helius API)
2. Gets 24h trading volume for each token (via DexScreener API)
3. Identifies the most recent token
4. Compares its volume to all other tokens from that wallet
5. Categorizes the wallet based on whether the most recent token has the highest volume

## Output Files

| File | Description |
|------|-------------|
| `wallets_with_highest_recent_volume.csv` | Wallets where the most recent token HAS the highest 24h volume |
| `wallets_without_highest_recent_volume.csv` | Wallets where the most recent token does NOT have the highest volume |
| `processed_wallets.log` | List of successfully processed wallets |
| `failed_wallets.log` | Wallets that failed with error details |
| `summary_report.txt` | Summary statistics of the run |

## CSV Format

Each CSV contains:
- `wallet_address` - The wallet that created the tokens
- `total_tokens_created` - Number of tokens created by this wallet
- `most_recent_token` - Address of the most recently created token
- `most_recent_token_symbol` - Symbol of the most recent token
- `recent_token_volume_24h` - 24h trading volume of the most recent token
- `highest_volume_token` - Address of the token with highest volume
- `highest_volume_amount` - The highest volume amount
- `all_tokens_data` - Summary of top 5 tokens by volume

## Resume Feature

If the script is interrupted (Ctrl+C or crash):
- Progress is saved automatically
- Simply run `python main.py` again to resume from where it left off
- Already processed wallets will be skipped

## Processing Speed

- Approximately 0.5-1 wallets per second
- 10,000 wallets: ~3-5 hours
- 50,000 wallets: ~15-25 hours

For large runs, it's recommended to run overnight.

## Troubleshooting

**"No tokens found" for a wallet:**
- The wallet may not have created any tokens
- The wallet may only hold tokens (not create them)

**Rate limiting (429 errors):**
- The script automatically retries with exponential backoff
- Failed wallets are logged and can be retried later

**Script crashes:**
- Just restart with `python main.py`
- It will resume from the last checkpoint

## Configuration (Advanced)

Edit these values in `main.py` if needed:

```python
RATE_LIMIT_DELAY = 0.15  # Seconds between wallets (increase if hitting rate limits)
MAX_WORKERS = 12         # Parallel threads (decrease if hitting rate limits)
MAX_RETRIES = 3          # Retry attempts on failure
```

## Support

If you encounter issues, check:
1. `failed_wallets.log` for specific errors
2. Your internet connection
3. That wallet addresses are valid Solana addresses
