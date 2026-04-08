from odoo import models, fields,api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    shopify_order_id = fields.Char("Shopify Order ID")

    @api.model
    def import_orders(self):
        configs = self.env['shopify.config'].search([])
        for config in configs:
            # Chỉ lấy đơn hàng mới từ lần sync cuối
            params = {}
            if config.last_sync_date:
                params['updated_at_min'] = config.last_sync_date.isoformat()

            data = config._make_request('orders', params=params)
            if not data: continue

            for s_order in data.get('orders', []):
                # Kiểm tra trùng
                if self.search([('shopify_order_id', '=', s_order['id'])]): continue

                # Tìm/Tạo khách hàng
                email = s_order.get('email')
                partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': s_order['customer']['first_name'] + " " + s_order['customer']['last_name'],
                        'email': email,
                    })

                # Tạo Order
                order_vals = {
                    'partner_id': partner.id,
                    'shopify_order_id': s_order['id'],
                    'warehouse_id': config.warehouse_id.id,
                    'order_line': []
                }
                
                # Thêm Line
                for line in s_order['line_items']:
                    product = self.env['product.product'].search([('default_code', '=', line['sku'])], limit=1)
                    if product:
                        order_vals['order_line'].append((0, 0, {
                            'product_id': product.id,
                            'product_uom_qty': line['quantity'],
                            'price_unit': line['price'],
                        }))
                
                new_order = self.create(order_vals)
                new_order.action_confirm() # Tự động xác nhận đơn