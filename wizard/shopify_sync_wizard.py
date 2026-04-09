from odoo import models, fields, api

class ShopifySyncWizard(models.TransientModel):
    _name = 'shopify.sync.wizard'
    _description = 'Wizard đồng bộ Shopify'

    # Cho phép người dùng chọn cửa hàng muốn sync
    config_id = fields.Many2one('shopify.config', string="Cửa hàng", required=True)
    
    sync_type = fields.Selection([
        ('product', 'Đồng bộ Sản phẩm'),
        ('order', 'Nhập Đơn hàng')
    ], string="Loại đồng bộ", default='product')

    def action_sync(self):
        """Nút bấm thực hiện hành động"""
        if self.sync_type == 'product':
            # Gọi hàm sync_products đã viết ở model product
            self.env['product.template'].sync_products()
        else:
            # Gọi hàm import_orders đã viết ở model sale.order
            self.env['sale.order'].import_orders()
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã bắt đầu quá trình đồng bộ {self.sync_type}',
                'type': 'success',
                'sticky': False,
            }
        }