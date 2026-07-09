#!/usr/bin/env python3

from tenable.asm.session import TenableASM
from tenable_collector import TenableCollector
from splunklib import modularinput as smi
import arrow
import traceback
import json

class TASM_Event_Proccessor(TenableCollector):

    PRODUCT = 'TASM'

    def _set_input_data(self) -> None:
        """Set Tenable OT input form fields and initialize tio object.
        """
        super(TASM_Event_Proccessor, self)._set_input_data()
        self.check_point_name = self.input_name
        self.get_checkpoint()
        try:
            self.tasm = TenableASM(
                api_key=self._account['tenable_easm_api_key'],
                url="https://{}".format(self._account["tenable_easm_domain"].strip("/")),
                proxies=self.proxies
            )
        except Exception as e:
            msg = f'Couldnt initialize Tenable ASM connection: {e}'
            self.log_error(f'message={msg}')
            raise Exception(msg)


    def create_events(self):
        ingested_count = 0
        try:
            self.log_info(f"Getting T.asm smart folders for mapping into events")
            self._build_smartfolder_lookup()
            self.log_info(f"Starting T.asm inventory collection and event creation")
            fetch_from = self.check_point.get('asm_last_metadata_change') or self.start_time_date
            search_params = (('bd.last_metadata_change', 'after', fetch_from),)
            for asset in self.tasm.inventory.list(*search_params, size=5000):
                asset['bd.smartfolders'] = self._update_smartfolders(asset.pop('bd.smartfolders'))
                if asset.get('bd.addedtoportfolio', False):
                    asset['bd.addedtoportfolio'] = self._convert_epoch_to_timestamp(asset.get('bd.addedtoportfolio'))
                clean_asset = json.dumps(self._strip_prefix_from_keys(asset))
                event = smi.Event(
                                    data=clean_asset,
                                    index=self.index,
                                    sourcetype="tenable:asm:assets",
                                    unbroken=True
                                )
                self.event_writer.write_event(event)
                ingested_count += 1
            self.log_info(f"Completed T.asm inventory collection and event creation")
        except Exception:
            self.log_error(f"Error in collecting the ASM data. Error: {traceback.format_exc()}.")
        finally:
            self.log_info(f"Total events ingested in Splunk: {ingested_count}.")
            if ingested_count > 0:
                self.check_point['asm_last_metadata_change'] = self.current_time_formatted
                self.save_checkpoint()

    def _convert_epoch_to_timestamp(self, epoch_time):
        time = arrow.get(epoch_time)
        return time.isoformat()

    def _strip_prefix_from_keys(self, asset):
        ret = {}
        for old_key in asset:
            if old_key.startswith('bd.'):
                key = old_key[3:]
            elif old_key.startswith('ports.'):
                key = old_key[6:]
            else:
                key = old_key
            ret[key] = asset[old_key]
        return ret

    def _update_smartfolders(self, smartfolders):
        ret = []
        if smartfolders == '':
            return ret
        else:
            tmp_ids = smartfolders.split(',')
            for s in tmp_ids:
                id = int(s[:len(s)-6])
                data = {
                    'id': id,
                    'name': self.smartfolders[id]
                }
                ret.append(data)
            return ret

    def _build_smartfolder_lookup(self):
        self.smartfolders = {}
        for sf in self.tasm.smart_folders.list():
            self.smartfolders[int(sf['id'])] = sf['name']
