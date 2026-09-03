# QR payload format

Spool QR codes contain the stable payload:

```text
fcc:spool:<code>
```

Example:

```text
fcc:spool:FIL-0007
```

`code` is the immutable public spool identifier. The payload contains no URL, host, network address, database ID, or mutable spool data.

## Internal resolution

The application resolves a spool QR payload locally before navigating:

```text
fcc:spool:FIL-0007
    ->
FIL-0007
    ->
/qr/spool/FIL-0007
```

`parseSpoolQrPayload` accepts only the canonical `fcc:spool:<code>` protocol
(apart from surrounding whitespace) and validates the current `FIL-XXXX` code
format. `buildSpoolQrLandingPath` then creates the internal mobile landing path.

The physical QR remains independent of the application's address. It does not
change when the application is opened through localhost, LAN, or Tailscale, and
it must not be replaced with an absolute HTTP or HTTPS URL.

## Browser scanner

The `/scan` page requests the client device camera only after the user selects
the start action. QR frames are decoded locally in the browser and are never
sent to the API or an external service. A valid payload is resolved through the
same parser and landing-path helper documented above.

Browser camera access normally requires a secure context: HTTPS or localhost.
Opening the application over a plain HTTP LAN or Tailscale IP can therefore
leave scanning unavailable even though the page itself works. In that case the
scanner explains the HTTPS requirement and keeps the manual `FIL-XXXX` fallback
available. The QR payload remains `fcc:spool:<code>` regardless of how the
application is reached.
