from odoo import models, fields, api
import logging

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _logger = logging.getLogger(__name__)

    shopify_order_id = fields.Char("Shopify Order ID")

    @api.model
    def import_orders(self, config_id=None):
        configs = config_id if config_id else self.env['shopify.config'].search([])
        for config in configs:
            # Only fetch new orders since last sync
            params = {}
            if config.last_sync_date:
                params['updated_at_min'] = config.last_sync_date.isoformat()

            try:
                data = config._make_request('orders', params=params)
                if not data:
                    continue

                for s_order in data.get('orders', []):
                    # Check for duplicates
                    if self.search([('shopify_order_id', '=', str(s_order['id']))]):
                        continue

                    # Handle customer (may be None for guest orders)
                    customer = s_order.get('customer')
                    email = s_order.get('email') if customer else None
                    partner = None
                    if email:
                        partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
                    if not partner and customer:
                        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                        if not name:
                            name = "Unknown Customer"
                        partner = self.env['res.partner'].create({
                            'name': name,
                            'email': email,
                        })
                    elif not partner:
                        # Skip or create a generic partner for guest orders
                        self._logger.warning(f"Skipping order {s_order['id']} due to missing customer data")
                        continue

                    # Create Order
                    order_vals = {
                        'partner_id': partner.id,
                        'shopify_order_id': str(s_order['id']),
                        'warehouse_id': config.warehouse_id.id,
                        'order_line': []
                    }
                    
                    # Add Lines
                    for line in s_order.get('line_items', []):
                        product = self.env['product.product'].search([('default_code', '=', line.get('sku'))], limit=1)
                        if product:
                            order_vals['order_line'].append((0, 0, {
                                'product_id': product.id,
                                'product_uom_qty': line.get('quantity', 1),
                                'price_unit': float(line.get('price', 0.0)),
                            }))
                        else:
                            self._logger.warning(f"Product not found for SKU {line.get('sku')} in order {s_order['id']}")
                    
                    new_order = self.create(order_vals)
                    # Optional: Only confirm if no issues (e.g., check lines exist)
                    if new_order.order_line:
                        new_order.action_confirm()
                
                config.write({'last_sync_date': fields.Datetime.now()})
            except Exception as e:
                self._logger.error(f"Error importing orders for config {config.id}: {str(e)}")