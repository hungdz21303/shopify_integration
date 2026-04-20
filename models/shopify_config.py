from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utils.shopify_order_processor import ShopifyOrderProcessor
from ..utils.shopify_api_client import ShopifyAPIClient
import logging

_logger = logging.getLogger(__name__)

class ShopifyConfig(models.Model):
    _name = "shopify.config"
    _description = "Shopify Store Configuration"

    name = fields.Char(string="Store Name", required=True)
    shop_url = fields.Char(string="Shop URL", required=True)
    api_token = fields.Char(string="Access Token", password=True, required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    last_sync_date = fields.Datetime(string="Last Sync")

    def action_test_connection(self):
        self.ensure_one()
        client = ShopifyAPIClient(self.shop_url, self.api_token)
        if client.request("shop"): # Gọi đúng tên hàm request
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Thành công",
                    "message": "Kết nối Shopify ổn định!",
                    "type": "success",
                },
            }

    def _make_request(self, endpoint, params=None):
        self.ensure_one()
        client = ShopifyAPIClient(self.shop_url, self.api_token)
        return client.request(endpoint, params=params)

    def import_orders(self):
        """Logic chính để kéo đơn hàng về Odoo"""
        self.ensure_one()
        params = {'status': 'any'}  # Có thể lấy mọi trạng thái đơn hàng

        # Chỉ lấy đơn hàng mới phát sinh sau lần đồng bộ cuối
        if self.last_sync_date:
            params['updated_at_min'] = self.last_sync_date.isoformat()

        data = self._make_request('orders', params=params)
        if not data or 'orders' not in data:
            return 0

        success_count = 0
        for order_data in data['orders']:
            # 1. Kiểm tra trùng lặp
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
                        # Ghi log cảnh báo nếu thiếu SKU nhưng không dừng tiến trình
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
                    # Tự động xác nhận đơn hàng
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
        self.write({'last_sync_date': fields.Datetime.now()})
        return success_count

    def import_orders_with_notification(self):
        self.ensure_one()
        count = self.import_orders()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đồng bộ đơn hàng',
                'message': f'Đã đồng bộ {count} đơn hàng từ {self.name}.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def import_products(self):
        """Hàm để đồng bộ sản phẩm"""
        self.ensure_one()

        try:
            # Gọi sync_products từ product.template
            self.env['product.template'].sudo().sync_products(self)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Đồng bộ sản phẩm',
                    'message': f'Đã đồng bộ sản phẩm từ {self.name}.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi đồng bộ sản phẩm',
                    'message': f'Không thể đồng bộ sản phẩm: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                },
            }

    def sync_all_products(self):
        """Đồng bộ toàn bộ sản phẩm và disable những sản phẩm không còn trong Shopify"""
        self.ensure_one()

        try:
            # Lấy tất cả sản phẩm từ Shopify
            data = self._make_request('products')
            if not data or 'products' not in data:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Lỗi đồng bộ sản phẩm',
                        'message': 'Không thể lấy dữ liệu sản phẩm từ Shopify.',
                        'type': 'danger',
                        'sticky': True,
                    },
                }

            shopify_product_ids = set()
            success_count = 0

            for s_prod in data.get('products', []):
                s_id = str(s_prod.get('id'))
                shopify_product_ids.add(s_id)

                # Handle Category
                cat_name = s_prod.get('product_type') or 'Uncategorized'
                category = self.env['product.category'].search([('name', '=', cat_name)], limit=1)
                if not category:
                    category = self.env['product.category'].create({'name': cat_name})

                # Upsert Product
                odoo_prod = self.env['product.template'].sudo().search([('shopify_id', '=', s_id)], limit=1)
                if not s_prod.get('title'):
                    continue

                vals = {
                    'name': s_prod['title'],
                    'description_sale': s_prod.get('body_html', ''),
                    'categ_id': category.id,
                    'shopify_id': s_id,
                    'sale_ok': True,
                    'purchase_ok': True,
                    'type': 'consu',
                    'shopify_config_id': self.id,
                    'active': True,  # Đảm bảo active
                }

                if odoo_prod:
                    odoo_prod.write(vals)
                else:
                    self.env['product.template'].sudo().create(vals)

                success_count += 1

            # Disable products không còn trong Shopify
            odoo_products = self.env['product.template'].sudo().search([
                ('shopify_config_id', '=', self.id),
                ('shopify_id', '!=', False)
            ])

            disabled_count = 0
            for product in odoo_products:
                if product.shopify_id not in shopify_product_ids:
                    product.write({'active': False})
                    disabled_count += 1

            # Cập nhật last_sync_date
            self.write({'last_sync_date': fields.Datetime.now()})

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Đồng bộ toàn bộ sản phẩm',
                    'message': f'Đã đồng bộ {success_count} sản phẩm, disabled {disabled_count} sản phẩm không còn tồn tại.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi đồng bộ sản phẩm',
                    'message': f'Lỗi: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                },
            }

    def action_sync_orders_cron(self):
        for config in self:
            config.import_orders()

    def action_sync_products_cron(self):
        for config in self:
            config.import_products()