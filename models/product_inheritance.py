from odoo import models, fields
import logging

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    _logger = logging.getLogger(__name__)
    shopify_id = fields.Char("Shopify ID", copy=False, index=True)
    # Optional: Add config_id to associate products with specific configs
    shopify_config_id = fields.Many2one('shopify.config', string="Shopify Config")

    def sync_products(self, config_id=None):
        configs = config_id if config_id else self.env['shopify.config'].search([])
        for config in configs:
            try:
                data = config._make_request('products')
                if not data or 'products' not in data:
                    self._logger.warning(f"No products data for config {config.id}")
                    continue
                
                for s_prod in data.get('products', []):
                    # 1. Handle Category
                    cat_name = s_prod.get('product_type') or 'Uncategorized'
                    category = self.env['product.category'].search([('name', '=', cat_name)], limit=1)
                    if not category:
                        category = self.env['product.category'].create({'name': cat_name})

                    # 2. Upsert Product
                    s_id = str(s_prod.get('id'))
                    odoo_prod = self.search([('shopify_id', '=', s_id)], limit=1)
                    if not s_prod.get('title'):
                        self._logger.warning(f"Skipping product {s_id} due to missing title")
                        continue
                    vals = {
                        'name': s_prod['title'],
                        'description_sale': s_prod.get('body_html', ''),
                        'categ_id': category.id,
                        'shopify_id': s_id,
                        'sale_ok': True,
                        'purchase_ok': True,
                        'type': 'consu',
                        'shopify_config_id': config.id,  # Associate with config
                    }
                    if odoo_prod:
                        odoo_prod.write(vals)
                    else:
                        self.create(vals)
                
                # Update last sync date properly
                config.write({'last_sync_date': fields.Datetime.now()})
            except Exception as e:
                self._logger.error(f"Error syncing products for config {config.id}: {str(e)}")