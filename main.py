"""
Solana Wallet Token Analyzer
Analyzes wallet addresses and categorizes them based on token deployment activity
Uses Helius API for token creation data + DexScreener for volume data
OPTIMIZED: Uses concurrent threading for parallel API calls
"""

import requests
import csv
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# CONFIGURATION

# Helius API Configuration
HELIUS_API_KEY = "db683a77-edb6-4c80-8cac-944640c07e21"
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# DexScreener for volume data
DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"

# Rate limiting - BALANCED (fast but safe)
RATE_LIMIT_DELAY = 0.15  # seconds between wallets
MAX_RETRIES = 3  # retry on rate limits
REQUEST_TIMEOUT = 12  # reasonable timeout
MAX_WORKERS = 12  # good parallelism

# File paths
INPUT_FILE = "wallets.txt"
PROCESSED_LOG = "processed_wallets.log"
FAILED_LOG = "failed_wallets.log"
HIGH_VOLUME_CSV = "wallets_with_highest_recent_volume.csv"
LOW_VOLUME_CSV = "wallets_without_highest_recent_volume.csv"
SUMMARY_FILE = "summary_report.txt"

# CSV Headers
CSV_HEADERS = [
    'wallet_address',
    'total_tokens_created',
    'most_recent_token',
    'most_recent_token_symbol',
    'recent_token_volume_24h',
    'highest_volume_token',
    'highest_volume_amount',
    'all_tokens_data'
]

# CHECKPOINT & LOGGING FUNCTIONS

def load_processed_wallets() -> Set[str]:
    """Load set of already processed wallet addresses from log file"""
    try:
        with open(PROCESSED_LOG, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def log_processed_wallet(wallet_address: str):
    """Append successfully processed wallet to log"""
    with open(PROCESSED_LOG, 'a') as f:
        f.write(f"{wallet_address}\n")

def log_failed_wallet(wallet_address: str, error_msg: str):
    """Log failed wallet with error message and timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(FAILED_LOG, 'a') as f:
        f.write(f"{wallet_address}|{error_msg}|{timestamp}\n")

# HELIUS API - GET TOKENS CREATED BY WALLET

def get_tokens_created_by_wallet(wallet_address: str, attempt: int = 1) -> Optional[List[Dict]]:
    """
    Use Helius DAS API to get fungible tokens created by a wallet address
    """
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "wallet-analyzer",
            "method": "getAssetsByCreator",
            "params": {
                "creatorAddress": wallet_address,
                "onlyVerified": False,
                "page": 1,
                "limit": 1000
            }
        }
        
        response = requests.post(
            HELIUS_RPC_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 429:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                return get_tokens_created_by_wallet(wallet_address, attempt + 1)
            return None
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data and 'items' in data['result']:
                tokens = []
                for item in data['result']['items']:
                    interface = item.get('interface', '')
                    if interface in ['FungibleToken', 'FungibleAsset'] or item.get('token_info'):
                        tokens.append({
                            'address': item.get('id', ''),
                            'symbol': item.get('content', {}).get('metadata', {}).get('symbol', 'UNKNOWN'),
                            'name': item.get('content', {}).get('metadata', {}).get('name', 'Unknown'),
                            'created_at': item.get('created_at', 0)
                        })
                return tokens
            return []
        
        if attempt < MAX_RETRIES:
            time.sleep(1)
            return get_tokens_created_by_wallet(wallet_address, attempt + 1)
        
        return None
        
    except Exception as e:
        if attempt < MAX_RETRIES:
            time.sleep(1)
            return get_tokens_created_by_wallet(wallet_address, attempt + 1)
        return None

# DEXSCREENER API - GET VOLUME DATA (THREAD-SAFE)

def get_token_volume(token_address: str) -> tuple:
    """
    Get 24h trading volume for a token from DexScreener
    Returns: (token_address, volume) tuple for easy mapping
    """
    try:
        url = f"{DEXSCREENER_BASE}/tokens/{token_address}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])
            total_volume = sum(float(p.get('volume', {}).get('h24', 0) or 0) for p in pairs)
            return (token_address, total_volume)
        
        return (token_address, 0.0)
        
    except:
        return (token_address, 0.0)

def fetch_volumes_concurrent(tokens: List[Dict]) -> Dict[str, float]:
    """
    Fetch volumes for multiple tokens CONCURRENTLY using ThreadPoolExecutor
    Returns: dict mapping token_address -> volume
    """
    volumes = {}
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all volume fetch tasks
        futures = {
            executor.submit(get_token_volume, token['address']): token['address']
            for token in tokens if token.get('address')
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                token_addr, volume = future.result()
                volumes[token_addr] = volume
            except:
                pass
    
    return volumes

# ALTERNATIVE: SEARCH DEXSCREENER DIRECTLY

def search_tokens_by_wallet(wallet_address: str) -> List[Dict]:
    """Alternative: Search DexScreener for tokens associated with wallet"""
    try:
        url = f"{DEXSCREENER_BASE}/search?q={wallet_address}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])
            
            tokens = {}
            for pair in pairs:
                token_addr = pair.get('baseToken', {}).get('address', '')
                if token_addr and token_addr not in tokens:
                    tokens[token_addr] = {
                        'address': token_addr,
                        'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                        'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                        'created_at': pair.get('pairCreatedAt', 0),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0) or 0)
                    }
                elif token_addr:
                    tokens[token_addr]['volume_24h'] += float(pair.get('volume', {}).get('h24', 0) or 0)
            
            return list(tokens.values())
    except:
        pass
    
    return []

# TOKEN ANALYSIS LOGIC - OPTIMIZED WITH CONCURRENT FETCHING

def analyze_wallet(wallet_address: str) -> Optional[Dict]:
    """
    Analyze tokens for a wallet with CONCURRENT volume fetching
    """
    print(f"  Fetching tokens...")
    
    # Try Helius first
    tokens = get_tokens_created_by_wallet(wallet_address)
    
    # Fallback to DexScreener
    if not tokens:
        tokens = search_tokens_by_wallet(wallet_address)
    
    if not tokens:
        log_failed_wallet(wallet_address, "No tokens found")
        return None
    
    print(f"  Found {len(tokens)} tokens")
    
    # Sort by creation time to find most recent
    tokens.sort(key=lambda x: (x.get('created_at', 0), x.get('address', '')), reverse=True)
    
    # Only analyze top 10 most recent tokens
    tokens_to_check = tokens[:10]
    
    # CONCURRENT volume fetching - much faster!
    print(f"  Fetching volumes (parallel)...")
    volumes = fetch_volumes_concurrent(tokens_to_check)
    
    # Apply volumes to tokens
    for token in tokens_to_check:
        token['volume_24h'] = volumes.get(token['address'], 0.0)
    
    tokens_with_data = [t for t in tokens_to_check if t.get('address')]
    
    if not tokens_with_data:
        log_failed_wallet(wallet_address, "No valid tokens")
        return None
    
    most_recent_token = tokens_with_data[0]
    highest_volume_token = max(tokens_with_data, key=lambda x: x.get('volume_24h', 0))
    has_highest_volume = (most_recent_token['address'] == highest_volume_token['address'])
    
    all_tokens_summary = "; ".join([
        f"{t.get('symbol', 'UNK')}(${t.get('volume_24h', 0):,.2f})"
        for t in sorted(tokens_with_data, key=lambda x: x.get('volume_24h', 0), reverse=True)[:5]
    ])
    
    return {
        'wallet_address': wallet_address,
        'total_tokens_created': len(tokens),
        'most_recent_token': most_recent_token.get('address', ''),
        'most_recent_token_symbol': most_recent_token.get('symbol', 'UNKNOWN'),
        'recent_token_volume_24h': most_recent_token.get('volume_24h', 0),
        'highest_volume_token': highest_volume_token.get('address', ''),
        'highest_volume_amount': highest_volume_token.get('volume_24h', 0),
        'all_tokens_data': all_tokens_summary,
        'has_highest_volume': has_highest_volume
    }

# CSV OUTPUT FUNCTIONS

def initialize_csv_files():
    """Create CSV files with headers if they don't exist"""
    for filename in [HIGH_VOLUME_CSV, LOW_VOLUME_CSV]:
        if not os.path.exists(filename):
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()

def write_to_csv(wallet_data: Dict):
    """Write wallet data to appropriate CSV file"""
    filename = (HIGH_VOLUME_CSV if wallet_data['has_highest_volume'] 
                else LOW_VOLUME_CSV)
    
    csv_data = {k: v for k, v in wallet_data.items() if k != 'has_highest_volume'}
    
    with open(filename, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(csv_data)

def add_summary_row():
    """Add summary row to CSV files"""
    for filename in [HIGH_VOLUME_CSV, LOW_VOLUME_CSV]:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if rows:
                total_wallets = len(rows)
                total_tokens = sum(int(row.get('total_tokens_created', 0)) for row in rows)
                avg_tokens = total_tokens / total_wallets if total_wallets > 0 else 0
                
                with open(filename, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                    writer.writeheader()
                    
                    summary_row = {
                        'wallet_address': f'SUMMARY: {total_wallets} wallets',
                        'total_tokens_created': f'{total_tokens} total tokens',
                        'most_recent_token': f'Avg: {avg_tokens:.1f} tokens/wallet',
                        'most_recent_token_symbol': '',
                        'recent_token_volume_24h': '',
                        'highest_volume_token': '',
                        'highest_volume_amount': '',
                        'all_tokens_data': ''
                    }
                    writer.writerow(summary_row)
                    
                    separator_row = {field: '---' for field in CSV_HEADERS}
                    writer.writerow(separator_row)
                    
                    writer.writerows(rows)

# SUMMARY REPORT

def generate_summary(total_wallets: int, successful: int, failed: int, skipped: int):
    """Generate final summary report"""
    high_volume_count = 0
    low_volume_count = 0
    
    if os.path.exists(HIGH_VOLUME_CSV):
        with open(HIGH_VOLUME_CSV, 'r') as f:
            high_volume_count = max(0, sum(1 for line in f) - 3)
    
    if os.path.exists(LOW_VOLUME_CSV):
        with open(LOW_VOLUME_CSV, 'r') as f:
            low_volume_count = max(0, sum(1 for line in f) - 3)
    
    report = f"""
{'='*60}
WALLET ANALYSIS SUMMARY REPORT
{'='*60}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

INPUT STATISTICS:
- Total wallet addresses in input file: {total_wallets}
- Already processed (skipped): {skipped}
- Wallets processed in this run: {total_wallets - skipped}

PROCESSING RESULTS:
- Successfully analyzed: {successful}
- Failed to process: {failed}
- Success rate: {(successful/(successful+failed)*100) if (successful+failed) > 0 else 0:.2f}%

CATEGORIZATION:
- Wallets with highest recent volume: {high_volume_count}
- Wallets without highest recent volume: {low_volume_count}

VALIDATION CHECK:
- Processed + Failed = {successful + failed}
- Should equal total processed = {total_wallets - skipped}
- Status: {'✓ PASS' if (successful + failed) == (total_wallets - skipped) else '✗ FAIL'}

OUTPUT FILES:
- High volume wallets: {HIGH_VOLUME_CSV}
- Low volume wallets: {LOW_VOLUME_CSV}
- Processed log: {PROCESSED_LOG}
- Failed log: {FAILED_LOG}

{'='*60}
"""
    
    with open(SUMMARY_FILE, 'w') as f:
        f.write(report)
    
    print(report)

# MAIN PROCESSING LOOP

def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("SOLANA WALLET TOKEN ANALYZER")
    print("SPEED OPTIMIZED - Parallel Processing Enabled")
    print("="*60 + "\n")
    
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: Input file '{INPUT_FILE}' not found!")
        return
    
    print(f"Loading wallet addresses from {INPUT_FILE}...")
    with open(INPUT_FILE, 'r') as f:
        all_wallets = [line.strip() for line in f if line.strip()]
    
    if not all_wallets:
        print("ERROR: No wallet addresses found!")
        return
    
    processed_wallets = load_processed_wallets()
    remaining_wallets = [w for w in all_wallets if w not in processed_wallets]
    
    print(f"\nSTATUS:")
    print(f"  Total wallets: {len(all_wallets)}")
    print(f"  Already done: {len(processed_wallets)}")
    print(f"  Remaining: {len(remaining_wallets)}")
    
    if not remaining_wallets:
        print("\n[OK] All wallets already processed!")
        return
    
    initialize_csv_files()
    
    print(f"\nStarting parallel processing...\n")
    
    successful_count = 0
    failed_count = 0
    start_time = time.time()
    
    for idx, wallet in enumerate(remaining_wallets, 1):
        elapsed = time.time() - start_time
        rate = idx / elapsed if elapsed > 0 else 0
        remaining = (len(remaining_wallets) - idx) / rate if rate > 0 else 0
        
        print(f"[{idx}/{len(remaining_wallets)}] {wallet[:8]}...{wallet[-6:]}")
        print(f"  Speed: {rate:.1f} wallets/sec | ETA: {int(remaining)}s")
        
        result = analyze_wallet(wallet)
        
        if result:
            write_to_csv(result)
            log_processed_wallet(wallet)
            successful_count += 1
            
            status = "[HIGH]" if result['has_highest_volume'] else "[Low]"
            print(f"  {status} | Tokens: {result['total_tokens_created']} | Vol: ${result['recent_token_volume_24h']:,.2f}")
        else:
            failed_count += 1
            print(f"  [FAIL] Failed")
        
        time.sleep(RATE_LIMIT_DELAY)
        print()
    
    total_time = time.time() - start_time
    
    print("Finalizing...")
    add_summary_row()
    
    generate_summary(
        total_wallets=len(all_wallets),
        successful=successful_count,
        failed=failed_count,
        skipped=len(processed_wallets)
    )
    
    print(f"\nDONE in {total_time:.1f}s!")
    print(f"  Speed: {len(remaining_wallets)/total_time:.2f} wallets/second")
    print(f"  Successful: {successful_count}")
    print(f"  Failed: {failed_count}\n")

# ENTRY POINT

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted - Progress saved. Run again to resume.")
    except Exception as e:
        print(f"\n\n[X] Error: {str(e)}")