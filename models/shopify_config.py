from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import json
import time


class ShopifyConfig(models.Model):
    _name = 'shopify.config'
    _description = 'Shopify Store Configuration'

    name = fields.Char(string='Store Name', required=True)
    shop_url = fields.Char(string='Shop URL', required=True)
    api_token = fields.Char(string='Access Token', password=True, required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    last_sync_date = fields.Datetime(string='Last Sync')

    def _make_request(self, endpoint, method='GET', params=None, json_data=None):
        clean_host = self.shop_url.replace('https://', '').replace('http://', '').strip('/')
        url = f"https://{clean_host}/admin/api/2021-01/{endpoint}.json"
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_token
        }
        try:
            res = requests.request(method, url, headers=headers, params=params, json=json_data)
            if res.status_code == 429:  # Rate limit exceeded
                time.sleep(2)
                return self._make_request(endpoint, method, params, json_data)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            self.env['shopify.log'].create({
                'config_id': self.id,
                'status': 'failed',
                'message': f"API Error: {str(e)}",
            })
            return False
    def action_test_connection(self):
        result = self._make_request('shop')
        if result:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 
                    'params': {'title': 'Success', 'message': 'Connected!', 'type': 'success'}}


