from odoo import fields
from .shopify_api_client import ShopifyAPIClient
import logging

_logger = logging.getLogger(__name__)

class ShopifyProductProcessor:
    def __init__(self, env, config):
        self.env = env
        self.config = config
        self.api = ShopifyAPIClient(config.shop_url, config.api_token)

    def fetch_and_process(self):
        params = {}
        if self.config.last_sync_date:
            last_sync = self.config.last_sync_date
            last_sync_dt = fields.Datetime.from_string(last_sync)
            params['updated_at_min'] = last_sync_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        data = self.api.request('products', params=params)
        if data is None or 'products' not in data:
            return None

        success_count = 0
        for product_data in data['products']:
            try:
                # Lấy variant đầu tiên làm sản phẩm chính
                variant = product_data.get('variants', [{}])[0] if product_data.get('variants') else {}

                # Tìm sản phẩm hiện có
                existing_product = self.env['product.product'].sudo().search([
                    ('shopify_product_id', '=', str(product_data['id']))
                ], limit=1)

                # Chuẩn bị dữ liệu sản phẩm
                product_vals = {
                    'name': product_data.get('title', 'Unknown Product'),
                    'default_code': variant.get('sku') or f"SHOPIFY_{product_data['id']}",
                    'list_price': float(variant.get('price', 0.0)),
                    'type': 'product',
                    'shopify_product_id': str(product_data['id']),
                    'shopify_config_id': self.config.id,
                }

                if existing_product:
                    # Cập nhật sản phẩm hiện có
                    existing_product.write(product_vals)
                else:
                    # Tạo sản phẩm mới
                    self.env['product.product'].sudo().create(product_vals)

                success_count += 1

            except Exception as exc:
                _logger.exception('Unable to import Shopify product %s: %s', product_data.get('id'), exc)
                continue

        return success_count

    def sync_all_products(self):
        """Sync tất cả sản phẩm và disable những sản phẩm không còn trong Shopify"""
        # Lấy tất cả sản phẩm từ Shopify (không filter theo thời gian)
        data = self.api.request('products')
        if data is None or 'products' not in data:
            return None

        shopify_product_ids = set()
        success_count = 0

        # Xử lý từng sản phẩm từ Shopify
        for product_data in data['products']:
            shopify_id = str(product_data['id'])
            shopify_product_ids.add(shopify_id)

            try:
                # Lấy variant đầu tiên
                variant = product_data.get('variants', [{}])[0] if product_data.get('variants') else {}

                # Tìm sản phẩm hiện có
                existing_product = self.env['product.product'].sudo().search([
                    ('shopify_product_id', '=', shopify_id)
                ], limit=1)

                # Chuẩn bị dữ liệu
                product_vals = {
                    'name': product_data.get('title', 'Unknown Product'),
                    'default_code': variant.get('sku') or f"SHOPIFY_{shopify_id}",
                    'list_price': float(variant.get('price', 0.0)),
                    'type': 'product',
                    'shopify_product_id': shopify_id,
                    'shopify_config_id': self.config.id,
                    'active': True,  # Đảm bảo sản phẩm active
                }

                if existing_product:
                    # Cập nhật sản phẩm hiện có
                    existing_product.write(product_vals)
                else:
                    # Tạo sản phẩm mới
                    self.env['product.product'].sudo().create(product_vals)

                success_count += 1

            except Exception as exc:
                _logger.exception('Unable to sync Shopify product %s: %s', shopify_id, exc)
                continue

        # Disable sản phẩm không còn trong Shopify
        odoo_products = self.env['product.product'].sudo().search([
            ('shopify_config_id', '=', self.config.id),
            ('shopify_product_id', '!=', False)
        ])

        disabled_count = 0
        for product in odoo_products:
            if product.shopify_product_id not in shopify_product_ids:
                product.write({'active': False})
                disabled_count += 1

        _logger.info('Disabled %d products that no longer exist in Shopify', disabled_count)
        return success_count