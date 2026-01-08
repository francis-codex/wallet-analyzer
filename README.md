# Solana Wallet Token Analyzer

Analyzes Solana wallet addresses to identify token creation patterns and categorize wallets based on **all-time trading volume**.

## Windows Installation & Setup

### Step 1: Install Python
1. Download Python from https://python.org/downloads/
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Restart your computer after installation

### Step 2: Download & Setup
1. Download and extract the project folder
2. Open Command Prompt (search "cmd" in Start menu)
3. Navigate to the project folder:
```cmd
cd C:\path\to\wallet-analyzer
```

### Step 3: Install Dependencies
```cmd
pip install requests
```

### Step 4: Create Executable (Optional)
To create a standalone .exe file:
```cmd
pip install pyinstaller
pyinstaller --onefile --name WalletAnalyzer main.py
```
The executable will be created in the `dist` folder.

## Usage

### Option A: Run Python Script
1. Create `wallets.txt` with one wallet address per line
2. Run:
```cmd
python main.py
```

### Option B: Run Executable
1. Create `wallets.txt` in the same folder as WalletAnalyzer.exe
2. Double-click WalletAnalyzer.exe

### Input File Format
Create `wallets.txt` with wallet addresses (one per line):
```
7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM
... more addresses ...
```

## How It Works

For each wallet address:
1. Fetches all tokens **created by** that wallet
2. Gets **all-time trading volume** for each token (via Birdeye API)
3. Identifies the **most recent** token (by creation date)
4. Compares its volume to all other tokens
5. Categorizes based on whether most recent token has highest volume

## Output Files

| File | Description |
|------|-------------|
| `wallets_with_highest_recent_volume.csv` | Most recent token HAS the highest volume |
| `wallets_without_highest_recent_volume.csv` | Most recent token does NOT have highest volume |
| `processed_wallets.log` | Successfully processed wallets |
| `failed_wallets.log` | Failed wallets with errors |
| `summary_report.txt` | Summary statistics |

## CSV Columns

- `wallet_address` - The wallet that created tokens
- `total_tokens_created` - Number of tokens created
- `most_recent_token` - Address of most recent token
- `most_recent_token_symbol` - Symbol of most recent token
- `recent_token_volume_alltime` - All-time volume of most recent token
- `highest_volume_token` - Token with highest volume
- `highest_volume_amount` - Highest volume amount
- `all_tokens_data` - Summary of top 5 tokens by volume

## Resume Feature

If interrupted (Ctrl+C or crash):
- Progress is saved automatically
- Run again to resume from where it left off
- Already processed wallets are skipped

## Processing Speed

- ~0.5-1 wallets per second
- 10,000 wallets: ~3-5 hours
- 50,000 wallets: ~15-25 hours

## Troubleshooting

**"No tokens found"**: Wallet hasn't created any tokens

**Rate limiting**: Script automatically retries with backoff

**Script crashes**: Just restart - it resumes from checkpoint

## Configuration (Advanced)

Edit these in `main.py` if needed:
```python
RATE_LIMIT_DELAY = 0.15  # Increase if hitting rate limits
MAX_WORKERS = 12         # Decrease if hitting rate limits
```
