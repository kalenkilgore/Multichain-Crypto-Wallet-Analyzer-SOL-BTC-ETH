import os
import requests
import argparse
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta

# Load Moralis API key from .env
load_dotenv()
MORALIS_API_KEY = os.getenv('MORALIS_API_KEY')

if not MORALIS_API_KEY:
    print('Moralis API key not found in .env file.')
    exit(1)

# Cache for crypto prices
price_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

# Supported chains mapping for Moralis
CHAIN_MAP = {
    'ETH': 'eth',
    'BNB': 'bsc',
    'MATIC': 'polygon',
    'SOL': 'solana',
    'AVAX': 'avalanche',
    'FTM': 'fantom',
    'ARB': 'arbitrum',
    'OP': 'optimism',
}

# BlockCypher API endpoint for Bitcoin
BLOCKCYPHER_API = "https://api.blockcypher.com/v1/btc/main"

headers = {
    'accept': 'application/json',
    'X-API-Key': MORALIS_API_KEY
}

def get_cached_price(coin_id):
    """Get price from cache if available and not expired"""
    if coin_id in price_cache:
        cached_data = price_cache[coin_id]
        if datetime.now() - cached_data['timestamp'] < timedelta(seconds=CACHE_DURATION):
            return cached_data['price']
    return None

def set_cached_price(coin_id, price):
    """Set price in cache with current timestamp"""
    price_cache[coin_id] = {
        'price': price,
        'timestamp': datetime.now()
    }

def get_btc_transactions(wallet):
    """Get Bitcoin transactions using BlockCypher API"""
    url = f"{BLOCKCYPHER_API}/addrs/{wallet}"
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f'Error fetching BTC transactions (status {resp.status_code}): {resp.text}')
            exit(1)
        return resp.json()
    except Exception as e:
        print(f'Error fetching BTC transactions: {e}')
        exit(1)

def get_btc_price():
    """Get Bitcoin price using multiple sources with caching"""
    cached_price = get_cached_price('bitcoin')
    if cached_price is not None:
        return cached_price

    sources = [
        lambda: requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()['bitcoin']['usd'],
        lambda: float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT").json()['price']),
        lambda: float(requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot").json()['data']['amount'])
    ]

    for get_price in sources:
        try:
            price = get_price()
            set_cached_price('bitcoin', price)
            return price
        except Exception as e:
            continue

    # If all sources fail, return a default price or raise an error
    raise Exception("Unable to fetch BTC price from any source")

def analyze_btc_transactions(wallet):
    """Analyze Bitcoin transactions"""
    data = get_btc_transactions(wallet)
    price = get_btc_price()
    
    # BlockCypher returns values in Satoshis (1e-8 BTC)
    total_received = float(data.get('total_received', 0)) / 1e8
    total_sent = float(data.get('total_sent', 0)) / 1e8
    
    return total_received, total_sent, price, 8  # Bitcoin uses 8 decimals

def get_transactions(wallet, chain, coin_symbol, limit=100):
    if coin_symbol == 'BTC':
        return get_btc_transactions(wallet)
    elif coin_symbol == 'SOL':
        # Get balance and tokens using Solana gateway
        balance_url = f'https://solana-gateway.moralis.io/account/mainnet/{wallet}/balance'
        portfolio_url = f'https://solana-gateway.moralis.io/account/mainnet/{wallet}/portfolio'
        swaps_url = f'https://solana-gateway.moralis.io/account/mainnet/{wallet}/swaps'
        transfers_url = f'https://solana-gateway.moralis.io/account/mainnet/{wallet}/transfers'
        
        try:
            # Get native balance
            balance_resp = requests.get(balance_url, headers=headers)
            if balance_resp.status_code != 200:
                print(f'Error: Invalid Solana wallet address or API error: {balance_resp.text}')
                exit(1)
            
            balance_data = balance_resp.json()
            native_balance = float(balance_data.get('solana', 0))  # Get SOL amount directly
            
            # Get portfolio data
            portfolio_resp = requests.get(portfolio_url, headers=headers)
            if portfolio_resp.status_code != 200:
                print(f'Error fetching SOL portfolio: {portfolio_resp.text}')
                exit(1)
                
            portfolio_data = portfolio_resp.json()
            
            # Get transfer history with pagination
            transfers_params = {
                'limit': min(100, limit) if limit > 0 else 100,
                'order': 'DESC'
            }
            transfers_resp = requests.get(transfers_url, headers=headers, params=transfers_params)
            transfers_data = []
            if transfers_resp.status_code == 200:
                transfers_data = transfers_resp.json()
            
            # Get swap history
            swaps_params = {
                'limit': min(100, limit) if limit > 0 else 100,
                'order': 'DESC'
            }
            swaps_resp = requests.get(swaps_url, headers=headers, params=swaps_params)
            swaps_data = []
            if swaps_resp.status_code == 200:
                swaps_data = swaps_resp.json()
            
            # Create transaction structure
            transactions = []
            
            # Add native balance as an incoming transaction if positive
            if native_balance > 0:
                transactions.append({
                    'amount': native_balance,
                    'to_address': wallet.lower(),
                    'from_address': ''
                })
            
            # Add transfer transactions
            if isinstance(transfers_data, dict) and 'result' in transfers_data:
                for transfer in transfers_data['result']:
                    if transfer.get('type') == 'sol':
                        amount = float(transfer.get('amount', 0))
                        if transfer.get('to_address') == wallet:
                            transactions.append({
                                'amount': amount,
                                'to_address': wallet.lower(),
                                'from_address': transfer.get('from_address', '')
                            })
                        elif transfer.get('from_address') == wallet:
                            transactions.append({
                                'amount': amount,
                                'from_address': wallet.lower(),
                                'to_address': transfer.get('to_address', '')
                            })
                            
                    # Check if we've reached the user's limit
                    if limit > 0 and len(transactions) >= limit:
                        break
            
            # Add swap transactions if we haven't reached the limit
            if limit == 0 or len(transactions) < limit:
                if isinstance(swaps_data, dict) and 'result' in swaps_data:
                    for swap in swaps_data['result']:
                        # Handle buy transactions
                        if swap.get('transactionType') == 'buy':
                            sold_token = swap.get('sold', {})
                            if sold_token.get('symbol') == 'SOL':
                                transactions.append({
                                    'amount': float(sold_token.get('amount', 0)),
                                    'from_address': wallet.lower(),
                                    'to_address': swap.get('pairAddress', '')
                                })
                        # Handle sell transactions
                        elif swap.get('transactionType') == 'sell':
                            bought_token = swap.get('bought', {})
                            if bought_token.get('symbol') == 'SOL':
                                transactions.append({
                                    'amount': float(bought_token.get('amount', 0)),
                                    'to_address': wallet.lower(),
                                    'from_address': swap.get('pairAddress', '')
                                })
                                
                        # Check if we've reached the user's limit
                        if limit > 0 and len(transactions) >= limit:
                            break
            
            return {'result': transactions[:limit] if limit > 0 else transactions}
            
        except Exception as e:
            print(f'Error fetching SOL data: {str(e)}')
            exit(1)
    else:
        url = f'https://deep-index.moralis.io/api/v2.2/{wallet}/erc20/transfers'
        params = {
            'chain': chain,
            'limit': min(100, limit) if limit > 0 else 100  # Max 100 per page, but respect user limit
        }
        
        all_transfers = []
        cursor = None
        
        try:
            while True:
                if cursor:
                    params['cursor'] = cursor
                    
                resp = requests.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    print(f'Error fetching transactions (status {resp.status_code}): {resp.text}')
                    exit(1)
                    
                data = resp.json()
                if isinstance(data, dict) and 'result' in data:
                    transfers = data['result']
                    all_transfers.extend(transfers)
                    
                    # Check if we've reached the user's limit
                    if limit > 0 and len(all_transfers) >= limit:
                        all_transfers = all_transfers[:limit]
                        break
                    
                    # Check if there are more pages
                    cursor = data.get('cursor')
                    if not cursor:
                        break
                else:
                    all_transfers.extend(data if isinstance(data, list) else [])
                    if limit > 0:
                        all_transfers = all_transfers[:limit]
                    break
                    
            return all_transfers
        except Exception as e:
            print(f'Error fetching ERC20 transfers: {e}')
            exit(1)

def get_native_transactions(wallet, chain, coin_symbol, limit=100):
    """Get native token transactions using Moralis API"""
    url = f'https://deep-index.moralis.io/api/v2.2/{wallet}'
    params = {
        'chain': chain,
        'limit': min(100, limit) if limit > 0 else 100  # Max 100 per page, but respect user limit
    }
    
    all_transactions = []
    cursor = None
    
    try:
        while True:
            if cursor:
                params['cursor'] = cursor
                
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                print(f'Error fetching native transfers (status {resp.status_code}): {resp.text}')
                exit(1)
                
            data = resp.json()
            if isinstance(data, dict) and 'result' in data:
                transactions = data['result']
                all_transactions.extend(transactions)
                
                # Check if we've reached the user's limit
                if limit > 0 and len(all_transactions) >= limit:
                    all_transactions = all_transactions[:limit]
                    break
                
                # Check if there are more pages
                cursor = data.get('cursor')
                if not cursor:
                    break
            else:
                all_transactions.extend(data if isinstance(data, list) else [])
                if limit > 0:
                    all_transactions = all_transactions[:limit]
                break
                
        return all_transactions
    except Exception as e:
        print(f'Error fetching native transactions: {e}')
        exit(1)

def get_token_price(chain, address):
    url = f'https://deep-index.moralis.io/api/v2.2/{address}/erc20?chain={chain}'
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f'Error fetching token price (status {resp.status_code}): {resp.text}')
        exit(1)
    return resp.json()['usdPrice']

def get_native_price(wallet, chain, coin_symbol):
    """Get native token price from multiple sources with caching"""
    coin_id = coin_symbol.lower()
    cached_price = get_cached_price(coin_id)
    if cached_price is not None:
        return cached_price

    # Try Moralis first
    try:
        url = f'https://deep-index.moralis.io/api/v2.2/erc20/{wallet}/price'
        params = {'chain': chain}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            price = float(resp.json().get('usdPrice', 0))
            if price > 0:
                set_cached_price(coin_id, price)
                return price
    except Exception:
        pass

    # Fallback sources
    sources = [
        lambda: requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd").json()[coin_id]['usd'],
        lambda: float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin_symbol}USDT").json()['price']),
        lambda: float(requests.get(f"https://api.coinbase.com/v2/prices/{coin_symbol}-USD/spot").json()['data']['amount'])
    ]

    for get_price in sources:
        try:
            price = get_price()
            set_cached_price(coin_id, price)
            return price
        except Exception:
            continue

    # If all sources fail, return a default price or raise an error
    raise Exception(f"Unable to fetch {coin_symbol} price from any source")

def get_sol_price(wallet):
    """Get SOL price from multiple sources with caching"""
    cached_price = get_cached_price('solana')
    if cached_price is not None:
        return cached_price

    # Try Moralis first
    try:
        url = 'https://solana-gateway.moralis.io/token/mainnet/So11111111111111111111111111111111111111112/price'
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            price_data = resp.json()
            if 'usdPrice' in price_data:
                price = float(price_data['usdPrice'])
                set_cached_price('solana', price)
                return price
    except Exception:
        pass

    # Fallback sources
    sources = [
        lambda: requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd").json()['solana']['usd'],
        lambda: float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT").json()['price']),
        lambda: float(requests.get("https://api.coinbase.com/v2/prices/SOL-USD/spot").json()['data']['amount'])
    ]

    for get_price in sources:
        try:
            price = get_price()
            set_cached_price('solana', price)
            return price
        except Exception:
            continue

    # If all sources fail, return a default price or raise an error
    raise Exception("Unable to fetch SOL price from any source")

def analyze_transactions(wallet, coin_symbol, chain, limit=100):
    if coin_symbol == 'BTC':
        return analyze_btc_transactions(wallet)
    
    inflow = 0.0
    outflow = 0.0
    decimals = 18  # Default for ETH and most ERC20 tokens
    price = 0.0
    
    if coin_symbol == 'SOL':
        try:
            txs = get_transactions(wallet, chain, coin_symbol, limit)
            price = get_sol_price(wallet)
            
            if 'result' in txs:
                transactions = txs['result']
            else:
                transactions = []
            
            for tx in transactions:
                if not tx.get('amount'):
                    continue
                
                value = float(tx.get('amount', '0'))  # Amount is already in SOL
                
                if tx.get('to_address', '').lower() == wallet.lower():
                    inflow += value
                elif tx.get('from_address', '').lower() == wallet.lower():
                    outflow += value
            
            decimals = 9
        except Exception as e:
            print(f'Error processing SOL transactions: {e}')
            exit(1)
    else:
        # Native coin (ETH, BNB, etc.)
        try:
            native_txs = get_native_transactions(wallet, chain, coin_symbol, limit)
            price = get_native_price(wallet, chain, coin_symbol)
            
            # Process native transactions
            if 'result' in native_txs:
                transactions = native_txs['result']
            else:
                transactions = native_txs if isinstance(native_txs, list) else []
                
            for tx in transactions:
                if not tx.get('value') and not tx.get('native_value'):
                    continue
                    
                # Try both value fields that Moralis might return
                value = float(tx.get('value') or tx.get('native_value') or '0') / 1e18  # Convert from Wei to ETH
                
                # Check both address formats Moralis might return
                to_address = tx.get('to_address', tx.get('to', '')).lower()
                from_address = tx.get('from_address', tx.get('from', '')).lower()
                
                if to_address == wallet.lower():
                    inflow += value
                elif from_address == wallet.lower():
                    outflow += value
                    
        except Exception as e:
            print(f'Error processing native transactions: {e}')
            print(f'Response data: {native_txs}')  # Debug print
            exit(1)

    # Round to 8 decimal places for consistency with BTC
    inflow = round(inflow, 8)
    outflow = round(outflow, 8)
    
    return inflow, outflow, price, decimals

def main(wallet_address, coin_symbol):
    # Validate coin symbol
    coin_symbol = coin_symbol.upper()
    if coin_symbol == 'BTC':
        chain = 'btc'
    elif coin_symbol not in CHAIN_MAP:
        print(f'Error: {coin_symbol} is not supported.')
        print(f'Supported coins: BTC, {", ".join(CHAIN_MAP.keys())}')
        exit(1)
    else:
        chain = CHAIN_MAP[coin_symbol]
    
    inflow, outflow, price, decimals = analyze_transactions(wallet_address, coin_symbol, chain)
    inflow_usd = inflow * price
    outflow_usd = outflow * price
    net_amount = inflow - outflow
    net_usd = inflow_usd - outflow_usd
    
    print(f'\nWallet: {wallet_address}')
    print(f'Total Received: {inflow:.8f} {coin_symbol} (${inflow_usd:,.2f})')
    print(f'Total Sent: {outflow:.8f} {coin_symbol} (${outflow_usd:,.2f})')
    print(f'Net Balance: {net_amount:.8f} {coin_symbol} (${net_usd:,.2f})')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze crypto wallet transactions')
    parser.add_argument('input', help='Wallet address and coin symbol, comma separated (e.g., 0x123abc...,ETH). Supported coins: BTC, ' + ", ".join(CHAIN_MAP.keys()))
    
    args = parser.parse_args()
    
    # Split the input into wallet and coin
    try:
        wallet_address, coin_symbol = args.input.split(',')
        wallet_address = wallet_address.strip()
        coin_symbol = coin_symbol.strip()
        if not wallet_address or not coin_symbol:
            raise ValueError
    except ValueError:
        print('Error: Input must be in the format "wallet_address,coin_symbol"')
        print('Example: 0x742d35Cc6634C0532925a3b844Bc454e4438f44e,ETH')
        exit(1)
        
    main(wallet_address, coin_symbol) 