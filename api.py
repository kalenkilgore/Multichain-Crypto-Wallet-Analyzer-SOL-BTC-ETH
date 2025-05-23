from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import requests

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:8000",
            "https://kalenkilgore.github.io",
            "https://multichain-crypto-wallet-analyzer-sol.onrender.com"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"]
    }
})

# Load Moralis API key from .env
load_dotenv()
MORALIS_API_KEY = os.getenv('MORALIS_API_KEY')

if not MORALIS_API_KEY:
    print('Moralis API key not found in .env file.')
    exit(1)

# Import functions from wallet_analyzer.py
from wallet_analyzer import (
    analyze_transactions,
    CHAIN_MAP
)

@app.route('/analyze', methods=['POST'])
def analyze_wallet():
    try:
        data = request.json
        wallet = data.get('wallet')
        coin = data.get('coin')
        limit = data.get('limit', 100)  # Default to 100 if not specified

        if not wallet or not coin:
            return jsonify({
                'error': 'Wallet address and coin symbol are required'
            }), 400

        # Validate coin symbol
        coin = coin.upper()
        if coin == 'BTC':
            chain = 'btc'
        elif coin not in CHAIN_MAP:
            return jsonify({
                'error': f'{coin} is not supported. Supported coins: BTC, {", ".join(CHAIN_MAP.keys())}'
            }), 400
        else:
            chain = CHAIN_MAP[coin]

        try:
            # Analyze transactions with limit
            inflow, outflow, price, decimals = analyze_transactions(wallet, coin, chain, limit)
            inflow_usd = inflow * price
            outflow_usd = outflow * price
            net_amount = inflow - outflow
            net_usd = inflow_usd - outflow_usd

            return jsonify({
                'wallet': wallet,
                'coin': coin,
                'received': f'{inflow:.8f}',
                'receivedUsd': f'{inflow_usd:,.2f}',
                'sent': f'{outflow:.8f}',
                'sentUsd': f'{outflow_usd:,.2f}',
                'net': f'{net_amount:.8f}',
                'netUsd': f'{net_usd:,.2f}',
                'transactionsAnalyzed': limit if limit > 0 else 'all'
            })
        except Exception as e:
            if "Unable to fetch" in str(e):
                # Price fetching error - return results without USD values
                return jsonify({
                    'wallet': wallet,
                    'coin': coin,
                    'received': f'{inflow:.8f}',
                    'receivedUsd': 'Price Unavailable',
                    'sent': f'{outflow:.8f}',
                    'sentUsd': 'Price Unavailable',
                    'net': f'{net_amount:.8f}',
                    'netUsd': 'Price Unavailable',
                    'transactionsAnalyzed': limit if limit > 0 else 'all',
                    'warning': 'Price data temporarily unavailable. USD values could not be calculated.'
                })
            else:
                raise

    except Exception as e:
        error_message = str(e)
        if "rate limit" in error_message.lower():
            error_message = "Service is experiencing high demand. Please try again in a few minutes."
        return jsonify({
            'error': error_message
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True) 