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

    # --- CÁC HÀM CẦN THÊM VÀO ---

    def action_sync_products_cron(self):
        """Hàm dành cho Cron Job chạy tự động đồng bộ sản phẩm"""
        for config in self:
            # Gọi đến hàm sync của product.template đã viết trước đó
            self.env['product.template'].sudo().sync_products(config)

    def action_sync_orders_cron(self):
        """Hàm dành cho Cron Job chạy tự động import đơn hàng"""
        for config in self:
            config.import_orders()

    def import_orders(self):
        """Logic chính để kéo đơn hàng về Odoo"""
        self.ensure_one()
        params = {'status': 'any'} # Có thể lấy mọi trạng thái đơn hàng
        
        # Chỉ lấy đơn hàng mới phát sinh sau lần đồng bộ cuối
        if self.last_sync_date:
            params['updated_at_min'] = self.last_sync_date.isoformat()

        data = self._make_request('orders', params=params)
        if not data or 'orders' not in data:
            return 0

        success_count = 0
        for order_data in data['orders']:
            # 1. Kiểm tra trùng lặp (Mục 4 Requirement)
            existing = self.env['sale.order'].sudo().search([
                ('shopify_order_id', '=', str(order_data['id']))
            ], limit=1)
            if existing:
                continue

            try:
                # 2. Xử lý khách hàng (Match email)
                customer_data = order_data.get('customer', {})
                email = customer_data.get('email')
                partner = self.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
                
                if not partner and email:
                    partner = self.env['res.partner'].sudo().create({
                        'name': f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}",
                        'email': email,
                        'phone': customer_data.get('phone'),
                        'type': 'contact',
                    })

                # 3. Tạo Order Line
                lines = []
                for item in order_data.get('line_items', []):
                    # Tìm product theo SKU
                    product = self.env['product.product'].sudo().search([
                        ('default_code', '=', item.get('sku'))
                    ], limit=1)
                    
                    if product:
                        lines.append((0, 0, {
                            'product_id': product.id,
                            'product_uom_qty': item.get('quantity'),
                            'price_unit': float(item.get('price')),
                        }))
                    else:
                        # Ghi log cảnh báo nếu thiếu SKU nhưng không dừng tiến trình (Mục 4)
                        self.env['shopify.log'].create({
                            'config_id': self.id,
                            'status': 'failed',
                            'sync_type': 'order',
                            'message': f"Bỏ qua dòng hàng: SKU {item.get('sku')} không tồn tại trong Odoo.",
                        })

                if lines:
                    # 4. Tạo Sale Order
                    order = self.env['sale.order'].sudo().create({
                        'partner_id': partner.id,
                        'shopify_order_id': str(order_data['id']),
                        'warehouse_id': self.warehouse_id.id,
                        'order_line': lines,
                    })
                    # Tự động xác nhận đơn hàng (Mục 4)
                    order.action_confirm()
                    success_count += 1

            except Exception as e:
                self.env['shopify.log'].create({
                    'config_id': self.id,
                    'status': 'failed',
                    'sync_type': 'order',
                    'message': f"Lỗi đơn hàng {order_data.get('id')}: {str(e)}",
                })

        # 5. Cập nhật last_sync sau khi xong
        self.last_sync_date = fields.Datetime.now()
        return success_count
