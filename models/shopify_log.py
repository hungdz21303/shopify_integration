from odoo import models, fields

class ShopifyLog(models.Model):
    _name = 'shopify.log'
    _description = 'Shopify Sync Logs'
    _order = 'create_date desc' # Hiện log mới nhất lên đầu tiên

    config_id = fields.Many2one('shopify.config', string="Store", readonly=True)
    
    sync_type = fields.Selection([
        ('product', 'Product Sync'),
        ('order', 'Order Import'),
        ('inventory', 'Inventory Sync')
    ], string="Sync Type", readonly=True)
    
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success')
    ], string="Status", readonly=True)
    
    message = fields.Text(string="Message", readonly=True)
    shopify_record_id = fields.Char(string="Shopify Record ID", readonly=True)