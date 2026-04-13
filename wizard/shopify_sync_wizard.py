from odoo import models, fields, api
from odoo.exceptions import UserError
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
        # Đảm bảo đã chọn cửa hàng
        if not self.config_id:
            raise UserError("Vui lòng chọn một cửa hàng để đồng bộ!")

        if self.sync_type == 'product':
            # Truyền config_id vào để hàm biết lấy API Key/URL từ đâu
            self.env['product.template'].sync_products(self.config_id)
        else:
            # Tương tự cho đơn hàng
            self.env['sale.order'].import_orders(self.config_id)
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thông báo',
                'message': f'Đã bắt đầu đồng bộ {self.sync_type} từ {self.config_id.name}',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}, # Đóng wizard sau khi bấm
            }
        }