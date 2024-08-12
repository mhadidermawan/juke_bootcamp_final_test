from odoo import models, fields, api,  _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

# Model Buku Perpustakaan
class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _sql_constraints = [
        ('isbn_code_unique', 'unique(isbn_code)', 'Kode ISBN harus unik!'),
        ('serial_number_unique', 'unique(serial_number)', 'Nomor Seri harus unik!'),
    ]

    def action_view_rentals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rental Transactions',
            'view_mode': 'tree,form',
            'res_model': 'library.rental',
            'domain': [('book_ids', 'in', self.id)],
            'context': dict(self.env.context, create=False),
        }

    name = fields.Char(string='Judul', required=True)
    category = fields.Selection([
        ('umum', 'Umum'),
        ('it', 'IT'),
        ('kesehatan', 'Kesehatan'),
        ('politik', 'Politik')
    ], string='Category', required=True)
    publish_date = fields.Date(string='Tanggal Terbit')
    author_ids = fields.Many2many('res.partner', string='Penulis')
    isbn_code = fields.Char(string='Kode ISBN', required=True, unique=True)
    serial_number = fields.Char(string='Serial Number', required=True, unique=True)
    rak_id = fields.Many2one('library.shelf', string='Rak')
    qty_available = fields.Integer(string='Qty Tersedia')
    author_id = fields.Many2one('res.partner', string='Author', domain=[('is_author', '=', True)])
    

    @api.model
    def create(self, vals):
        record = super(LibraryBook, self).create(vals)
        record._update_author_books()
        return record

    def write(self, vals):
        res = super(LibraryBook, self).write(vals)
        self._update_author_books()
        return res

    def _update_author_books(self):
        for book in self:
            if book.author_ids:
                book.author_ids.write({'book_ids': [(4, book.id)]})

    @api.depends('author_ids')
    def _compute_authors_names(self):
        for record in self:
            record.authors_names = ', '.join(record.author_ids.mapped('name'))

    authors_names = fields.Char(string='Authors', compute='_compute_authors_names', store=True)

    def update_qty_available(self, qty):
        self.ensure_one()
        new_qty = self.qty_available - qty
        if new_qty < 0:
            raise ValidationError("Jumlah buku yang tersedia tidak mencukupi!")
        self.write({'qty_available': new_qty})

# Model Member Perpustakaan
class LibraryMember(models.Model):
    _name = 'library.member'
    _description = 'Library Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    identity_number = fields.Char(string='No Identitas', required=True, unique=True)
    identity_type = fields.Selection([
        ('ktp', 'KTP'),
        ('sim', 'SIM'),
        ('passport', 'Passport')
    ], string='Jenis Kartu Identitas', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', track_visibility='onchange')
    manager_id = fields.Many2one('res.users', string='Manager')

    show_send_for_approval = fields.Boolean(compute='_compute_show_send_for_approval')
    show_approve_reject = fields.Boolean(compute='_compute_show_approve_reject')

    @api.depends('state')
    def _compute_show_send_for_approval(self):
        for record in self:
            record.show_send_for_approval = record.state == 'draft'

    @api.depends('state')
    def _compute_show_approve_reject(self):
        for record in self:
            record.show_approve_reject = record.state == 'pending'

    @api.model
    def create(self, vals):
        vals['state'] = 'draft'
        member = super(LibraryMember, self).create(vals)
        
        if member.manager_id:
            member.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=member.manager_id.id,
                summary=_('New Member Approval Needed'),
                note=_('Please review and approve the new member: %s' % member.name),
            )
        
        return member

    def action_send_for_approval(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'pending'
                if record.manager_id:
                    record.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=record.manager_id.id,
                        summary=_('Member Approval Request'),
                        note=_('Please review and approve the new member: %s' % record.name),
                    )

    def action_approve(self):
        for record in self:
            if record.state == 'pending':
                record.state = 'approved'
                record.activity_feedback(['mail.mail_activity_data_todo'])
        
    def action_reject(self):
        for record in self:
            if record.state == 'pending':
                record.state = 'rejected'
                record.activity_feedback(['mail.mail_activity_data_todo'])

    
    
# Model Transaksi Rental
class LibraryRental(models.Model):
    _name = 'library.rental'
    _description = 'Library Rental'

    rental_date = fields.Date(string='Tanggal Rental', required=True)
    member_id = fields.Many2one('library.member', string='Nama Peminjam', required=True)
    book_ids = fields.Many2many('library.book', string='List Buku yang Dipinjam')
    location = fields.Char(string='Lokasi')
    qty_borrowed = fields.Integer(string='Jumlah Buku Dipinjam')
    start_date = fields.Date(string='Tanggal Mulai', compute='_compute_start_date', store=True)
    end_date = fields.Date(string='Tanggal Selesai', required=True)
    rental_duration = fields.Integer(string='Lama Peminjaman (Hari)', compute='_compute_rental_duration', store=True)
    total_rental_fee = fields.Float(string='Total Biaya Sewa')
    state = fields.Selection([
        ('in_progress', 'Sedang Dipinjam'),
        ('not_returned', 'Belum Dikembalikan'),
        ('done', 'Selesai')
    ], string='Status Transaksi', default='in_progress')

    @api.depends('rental_date')
    def _compute_start_date(self):
        for record in self:
            record.start_date = record.rental_date

    @api.depends('start_date', 'end_date')
    def _compute_rental_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                duration = (record.end_date - record.start_date).days
                record.rental_duration = duration
            else:
                record.rental_duration = 0

    @api.constrains('rental_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.rental_date > record.end_date:
                raise ValidationError('Tanggal rental tidak boleh lebih dari tanggal selesai.')
    
    @api.constrains('qty_borrowed', 'book_ids')
    def _check_qty_available(self):
        for record in self:
            for book in record.book_ids:
                if record.qty_borrowed > book.qty_available:
                    raise ValidationError(f'Jumlah buku "{book.name}" yang dipinjam melebihi stok yang tersedia!')

    @api.constrains('member_id')
    def _check_member_status(self):
        for record in self:
            if record.member_id.state == 'rejected':
                raise ValidationError(f'Anggota "{record.member_id.name}" telah ditolak dan tidak dapat melakukan transaksi rental!')

    @api.model
    def create(self, vals):
        rental = super(LibraryRental, self).create(vals)
        rental._update_book_qty(decrease=True)
        return rental

    def write(self, vals):
        res = super(LibraryRental, self).write(vals)
        
        if 'state' in vals and vals['state'] == 'done':
            self._return_books()
        else:
            self._update_book_qty(decrease=True)

        return res

    def _update_book_qty(self, decrease=False):
        for rental in self:
            if rental.book_ids:
                for book in rental.book_ids:
                    if decrease:
                        book.qty_available -= rental.qty_borrowed
                    else:
                        book.qty_available += rental.qty_borrowed

    def _return_books(self):
        for rental in self:
            if rental.book_ids and rental.state != 'done':
                self._update_book_qty(decrease=False)

    def action_done(self):
        for rental in self:
            if rental.state == 'done':
                raise ValidationError("Transaksi ini sudah selesai.")
            self._return_books()
            rental.write({'state': 'done'})


#Model Button Pada Master Penulis
class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_author = fields.Boolean(string='Is Author')
    book_ids = fields.Many2many('library.book', 'author_id', string='Books Written')

    def action_view_authored_books(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Authored Books',
            'view_mode': 'tree,form',
            'res_model': 'library.book',
            'domain': [('author_ids', 'in', self.id)],
            'context': dict(self.env.context, create=False),
        }
    
#Model Untuk Rak Buku
class LibraryShelf(models.Model):
    _name = 'library.shelf'
    _description = 'Library Shelf'

    name = fields.Char(string='Nama Rak', required=True)
    location = fields.Char(string='Lokasi Rak')
    book_ids = fields.One2many('library.book', 'rak_id', string='Buku di Rak')


class RentalReportWizard(models.TransientModel):
    _name = 'rental.report.wizard'
    _description = 'Wizard untuk Report Transaksi Rental'

    start_date = fields.Date(string='Tanggal Mulai', required=True)
    end_date = fields.Date(string='Tanggal Selesai', required=True)
    member_ids = fields.Many2many('library.member', string='Peminjam')

    def action_print_report(self):
        domain = [('rental_date', '>=', self.start_date), ('rental_date', '<=', self.end_date)]
        if self.member_ids:
            domain.append(('member_id', 'in', self.member_ids.ids))
        records = self.env['library.rental'].search(domain)

        if not records:
            raise ValidationError("Tidak ada transaksi rental yang ditemukan dalam rentang waktu yang dipilih.")

        return self.env.ref('koleksi_buku.report_rental_transaction_action').report_action(records)

class ReportRentalTransaction(models.AbstractModel):
    _name = 'report.koleksi_buku.report_rental_transaction'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['library.rental'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'library.rental',
            'docs': docs,
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'member_ids': data.get('member_ids'),
        }