import requests
import time
import logging

_logger = logging.getLogger(__name__)

class ShopifyAPIClient:
    def __init__(self, shop_url, api_token):
        # Làm sạch URL để tránh lỗi format
        self.shop_url = shop_url.replace('https://', '').replace('http://', '').strip('/')
        self.api_token = api_token
        self.version = '2024-04' # Sử dụng version ổn định

    def request(self, endpoint, method='GET', params=None, json_data=None):
        """Hàm duy nhất dùng để gọi API Shopify"""
        url = f"https://{self.shop_url}/admin/api/{self.version}/{endpoint}.json"
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_token
        }
        try:
            res = requests.request(method, url, headers=headers, params=params, json=json_data)
            if res.status_code == 429:  # Rate limit
                time.sleep(2)
                return self.request(endpoint, method, params, json_data)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            _logger.error("Shopify API Error: %s", str(e))
            return None