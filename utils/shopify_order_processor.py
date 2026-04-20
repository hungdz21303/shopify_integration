from odoo import fields
from .shopify_api_client import ShopifyAPIClient

class ShopifyOrderProcessor:
    def __init__(self, env, config):
        self.env = env
        self.config = config
        self.api = ShopifyAPIClient(config.shop_url, config.api_token)

    def fetch_and_process(self):
        params = {'status': 'any'}
        if self.config.last_sync_date:
            last_sync = self.config.last_sync_date
            last_sync_dt = fields.Datetime.from_string(last_sync)
            params['updated_at_min'] = last_sync_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        data = self.api.request('orders', params=params)
        if data is None or 'orders' not in data:
            return None

        success_count = 0
        for order_data in data['orders']:
            # Kiểm tra trùng lặp đơn hàng dựa trên ID Shopify
            if self.env['sale.order'].sudo().search_count([('shopify_order_id', '=', str(order_data['id']))]):
                continue

            try:
                # 1. Xử lý Đối tác (Partner)
                cust = order_data.get('customer', {})
                email = cust.get('email') or f"guest_{order_data['id']}@noemail.com"
                partner = self.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].sudo().create({
                        'name': f"{cust.get('first_name', '')} {cust.get('last_name', '')}" or "Shopify Customer",
                        'email': email,
                    })

                # 2. Xử lý Order Lines & Sản phẩm
                lines = []
                for item in order_data.get('line_items', []):
                    sku = item.get('sku')
                    product = self.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                    
                    if not product and sku: # Tạo sản phẩm nếu chưa có để demo trơn tru
                        product = self.env['product.product'].sudo().create({
                            'name': item.get('name'),
                            'default_code': sku,
                            'list_price': float(item.get('price', 0)),
                            'type': 'consu',
                        })
                    
                    if product:
                        lines.append((0, 0, {
                            'product_id': product.id,
                            'product_uom_qty': item.get('quantity'),
                            'price_unit': float(item.get('price')),
                        }))

                # 3. Tạo Đơn hàng
                if lines:
                    order = self.env['sale.order'].sudo().create({
                        'partner_id': partner.id,
                        'shopify_order_id': str(order_data['id']),
                        'warehouse_id': self.config.warehouse_id.id,
                        'order_line': lines,
                    })
                    order.action_confirm()
                    success_count += 1
            except Exception:
                continue
                
        return success_count