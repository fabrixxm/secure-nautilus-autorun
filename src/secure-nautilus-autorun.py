#!/usr/bin/env python2
# -*- encoding: utf-8 -*-
""" secure-nautilus-autorun

    Copyright (C) 2010 Fabio Comuni <fabrix.xm@gmail.com>

    secure-nautilus-autorun is free software; you can redistribute it and/or
    modify it under the terms of the GNU Library General Public License as
    published by the Free Software Foundation version 3

    secure-nautilus-autorun is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Library General Public License for more details.

    You should have received a copy of the GNU Library General Public
    License along with the Gnome Library; see the file COPYING. If not,
    write to the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
    Boston, MA 02111-1307, USA.

    Author: Fabio Comuni <fabrix.xm@gmail.com>

    Original nautilus-autorun-software C code:
        Copyright (C) 2008 Red Hat, Inc.
        Author: David Zeuthen <davidz@redhat.com>
"""


## original
## http://nautilus.sourcearchive.com/documentation/2.22.2/nautilus-autorun-software_8c-source.html
## docs
## http://library.gnome.org/devel/pygtk/stable/
## http://library.gnome.org/devel/pygobject/stable/
__author__ = "Fabio Comuni"
__version__ = "0.1"

import gnupg
import gettext
import gio
import gnome
import gnome.ui
import gtk
import sys
import subprocess

_ = gettext.gettext

gpg = gnupg.GPG()

def autorun_software_dialog_mount_unmounted(mount, dialog):
    mount.disconnect_by_func(autorun_software_dialog_mount_unmounted)
    dialog.destroy()



def checkfile(mount_root, file_path, must_be_executable):
    file = mount_root.get_child(file_path)
    try:
        file_info = file.query_info(gio.FILE_ATTRIBUTE_ACCESS_CAN_EXECUTE,
                                    gio.FILE_QUERY_INFO_NONE)
    except gio.Error:
        return False
    
    if must_be_executable and not file_info.get_attribute_boolean(gio.FILE_ATTRIBUTE_ACCESS_CAN_EXECUTE):
        return False
    
    return True



def find_autorun(mount):
    root = mount.get_root()
    
    program_to_spawn = None
    verification = None
    
    for f in ['.autorun','autorun','autorun.sh']:
        if checkfile(root, f, True):
            program_to_spawn = root.get_child(f)
            break;
    
    
    if checkfile(root, program_to_spawn.get_basename()+".gpg", False):
        try:
            verification = gpg.verify_file( open(program_to_spawn.get_path()+".gpg", "rb") )
        except Exception:
            pass

    return  program_to_spawn, verification

def autorun(mount, program_to_spawn):
    root = mount.get_root()
    path_to_spawn = program_to_spawn.get_path();

    cwd_for_program = root.get_path()
    
    try:
        pid = subprocess.Popen([path_to_spawn,], cwd=cwd_for_program).pid
    except Exception, err:
            d = gtk.MessageDialog(None,
                          type=gtk.MESSAGE_ERROR, 
                          buttons=gtk.BUTTONS_OK, 
                          message_format=str(err))
            d.set_title(_("Autorun on \"%s\"")%mount.get_name())
            d.run()
            d.destroy()
            

def present_autorun_for_software_dialog(mount):
    
    mount_name = mount.get_name()
    
    #*** star trek future is near ***
    program_to_spawn, verification = find_autorun(mount)
    if not program_to_spawn:
        return

    if verification!=None and verification.valid:
        ## check if we have private key for this signature
        if len([ k for k in gpg.list_keys(True) if k['keyid']==verification.key_id ])>0:
            autorun(mount, program_to_spawn)
            return
    
    
    dialog = gtk.MessageDialog(None, type=gtk.MESSAGE_OTHER, buttons=gtk.BUTTONS_CANCEL)
    dialog.set_markup( _("<big><b>This medium contains software intended to be automatically started. Would you like to run it?</b></big>") )
    secondary_text =  _("The software will run directly from the medium \"%s\". "
                        "You should never run software that you don't trust.\n"
                        "\n"
                        "If in doubt, press Cancel.") % mount_name
    
    icons = mount.get_icon()
    icon_theme = gtk.icon_theme_get_default()
    #how translate gtk.ICON_SIZE_DIALOG to a pixel size? boh...
    icon_info = icon_theme.choose_icon( icons.get_names(), 48, 0 )
    icon_pixbuf = icon_info.load_icon()
    
    
    image = gtk.Image()
    image.set_from_pixbuf(icon_pixbuf)
    image.set_alignment(0.5,0.0)
    dialog.set_image(image)
    
    dialog.set_title(mount_name)
    dialog.set_icon(icon_pixbuf)

    mount.connect("unmounted", autorun_software_dialog_mount_unmounted, dialog)
    
    dialog.add_button(_("_Run"), gtk.RESPONSE_OK)
    
    if verification!=None:
        if verification.valid:
            signed_button = gtk.Button(_("Signed"))
            signed_button_image = gtk.Image()
            signed_button_image.set_from_pixbuf(icon_theme.load_icon("gdu-encrypted-lock", 24, 0))
            signed_button.set_image(signed_button_image)
            dialog.add_action_widget( signed_button, gtk.RESPONSE_HELP)
            key_user = verification.username.replace("<","&lt;").replace(">","&gt;")
            secondary_text += "\n\n<small><b>autorun signed by %s</b></small>"%key_user
        else:
            signed_button = gtk.Button(_("Sign detail"))
            signed_button_image = gtk.Image()
            signed_button_image.set_from_pixbuf(icon_theme.load_icon("gdu-encrypted-unlock", 24, 0))
            signed_button.set_image(signed_button_image)
            dialog.add_action_widget( signed_button, gtk.RESPONSE_HELP)
            key_user = verification.username.replace("<","&lt;").replace(">","&gt;")
            secondary_text += "\n\n<b>Invalid sign by %s</b>"%key_user

    dialog.format_secondary_markup( secondary_text )
    dialog.show_all()
    
    ret = gtk.RESPONSE_HELP
    while ret == gtk.RESPONSE_HELP:
        ret = dialog.run()
        if ret == gtk.RESPONSE_HELP:
            d = gtk.MessageDialog(None,
                          type=gtk.MESSAGE_OTHER, 
                          buttons=gtk.BUTTONS_OK)
            d.set_markup("<tt>%s%s%s</tt>"%  ( "-"*80 , verification.stderr.replace("<","&lt;").replace(">","&gt;"), "-"*80))
            d.set_title("autorun signed by %s"%verification.username)
            d.set_icon(icon_pixbuf)
            d.run()
            d.destroy()
            

    dialog.destroy()
    if ret == gtk.RESPONSE_OK:
        autorun(mount, program_to_spawn)


if __name__=="__main__":
    # use nautilus translations
    # TODO: custom translations with new strings
    gettext.bindtextdomain("nautilus", "/usr/share/locale")
    gettext.bind_textdomain_codeset("nautilus", "UTF-8")
    gettext.textdomain("nautilus")
    
    
    app = gnome.program_init ("secure-nautilus-autorun", __version__,
                               gnome.libgnome_module_info_get(), sys.argv, []);


    if len(sys.argv)!=2:
        sys.exit(0)

    # instantiate monitor so we get the "unmounted" signal properly
    monitor = gio.volume_monitor_get()
    if not monitor:
        sys.exit(-1)
    
    file = gio.File(sys.argv[1])
    if not file:
        sys.exit(-2)

    mount = file.find_enclosing_mount()
    if not mount:
        sys.exit(-3)
    
    
    present_autorun_for_software_dialog (mount)
    

    
