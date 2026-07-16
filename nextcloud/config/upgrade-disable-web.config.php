<?php
// The container image owns the code; upgrades happen by deploying a new
// image, never through the web updater.
$CONFIG = array(
  'upgrade.disable-web' => true,
);
