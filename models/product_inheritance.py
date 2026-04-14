from odoo import models, fields
import logging
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    _logger = logging.getLogger(__name__)
    shopify_id = fields.Char("Shopify ID", copy=False, index=True)

    def sync_products(self, config_id=None):
        configs = config_id if config_id else self.env['shopify.config'].search([])
        for config in configs:
            data = config._make_request('products')
            if not data or 'products' not in data:
                continue
            
            for s_prod in data.get('products', []):
                # 1. Xử lý Category
                cat_name = s_prod.get('product_type') or 'Uncategorized'
                category = self.env['product.category'].search([('name', '=', cat_name)], limit=1)
                if not category:
                    category = self.env['product.category'].create({'name': cat_name})

                # 2. Upsert Product
                s_id = str(s_prod.get('id'))
                odoo_prod = self.search([('shopify_id', '=', s_prod['id'])], limit=1)
                vals = {
                    'name': s_prod['title'],
                    'description_sale': s_prod['body_html'],
                    'categ_id': category.id,
                    'shopify_id': s_prod['id'],
                    'sale_ok': True,
                    'purchase_ok': True,
                    'type': 'consu',
                }
                if odoo_prod:
                    odoo_prod.write(vals)
                else:
                    self.create(vals)
            
            config.last_sync_date = fields.Datetime.now()